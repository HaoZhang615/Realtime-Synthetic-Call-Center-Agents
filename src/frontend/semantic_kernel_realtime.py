# Copyright (c) Microsoft. All rights reserved.
import asyncio
import logging
import os
import json
import base64
import numpy as np
from typing import Any, List, Dict, Optional, Callable, Union
from datetime import datetime

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import (
    AzureRealtimeExecutionSettings,
    AzureRealtimeWebsocket,
    ListenEvents,
    TurnDetection,
)
from semantic_kernel.contents import AudioContent, ChatHistory, RealtimeAudioEvent, RealtimeTextEvent
from semantic_kernel.functions import kernel_function

from assistant_service import AssistantService
"""Register agent functions from the agents folder with the Kernel."""
# Import agent dictionaries
from agents.assistant_agent import assistant_agent
from agents.database_agent import database_agent
from agents.internal_kb import internal_kb_agent
from agents.web_search_agent import web_search_agent  
from agents.root import root_assistant

from chainlit.logger import logger

import util
util.load_dotenv_from_azd()

def float_to_16bit_pcm(float32_array):
    """
    Converts a numpy array of float32 amplitude data to a numpy array in int16 format.
    :param float32_array: numpy array of float32
    :return: numpy array of int16
    """
    int16_array = np.clip(float32_array, -1, 1) * 32767
    return int16_array.astype(np.int16)

def base64_to_array_buffer(base64_string):
    """
    Converts a base64 string to a numpy array buffer.
    :param base64_string: base64 encoded string
    :return: numpy array of uint8
    """
    binary_data = base64.b64decode(base64_string)
    return np.frombuffer(binary_data, dtype=np.uint8)

def array_buffer_to_base64(array_buffer: Union[np.ndarray, bytes, bytearray]) -> str:
    """
    Converts a numpy array buffer or bytes object to a base64 string.
    :param array_buffer: numpy array, bytes, or bytearray
    :return: base64 encoded string
    """
    # If it's already bytes or bytearray, encode it directly
    if isinstance(array_buffer, (bytes, bytearray)):
        return base64.b64encode(array_buffer).decode('utf-8')
    
    # If it's a numpy array, convert based on dtype
    if isinstance(array_buffer, np.ndarray):
        if array_buffer.dtype == np.float32:
            array_buffer = float_to_16bit_pcm(array_buffer)
        
        # Convert to bytes
        array_buffer = array_buffer.tobytes()
    
    # Encode to base64
    return base64.b64encode(array_buffer).decode('utf-8')

class ChainlitWebAudioHandler:
    """
    Audio handler that works with Chainlit's web interface instead of local audio devices.
    This replaces the dependency on sounddevice and allows audio to flow between browser and server.
    """
    
    def __init__(self, realtime_client=None):
        self.realtime_client = realtime_client
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def send_audio(self, audio_data):
        """Send audio data to the realtime client."""
        if self.realtime_client:
            audio_base64 = array_buffer_to_base64(audio_data)
            await self.realtime_client.send(
                RealtimeAudioEvent(audio=AudioContent(data=audio_base64))
            )
    
    async def client_callback(self, content):
        """
        This is a placeholder for audio output callback.
        In the Chainlit context, actual audio playback is handled by the browser.
        """
        # The actual audio handling is done by dispatching events that 
        # Chainlit's event handlers will process
        return content

class RealtimeConversationHandler:
    """
    Handles realtime conversation using Semantic Kernel's AzureRealtimeWebsocket.
    Adapted for web-based audio in Chainlit rather than local audio devices.
    """
    def __init__(self, customer_id: str = None):
        self.customer_id = customer_id
        self.kernel = Kernel()
        self.assistant_service = AssistantService()
        self.register_agents()
        self.chat_history = ChatHistory()
        self.realtime_agent = None
        self.web_audio_handler = None
        self.event_callbacks = {
            "text_received": [],
            "transcript_received": [],
            "audio_received": [],
            "item_completed": [],
            "agent_switched": []
        }
        # Buffer for audio data sent from the client
        self._audio_buffer = bytearray()

    def register_agents(self):
        """Register agent functions from the agents folder with the Kernel."""
        # Register agents with the assistant service
        # Note: These are dictionaries, not functions, so don't call them with ()
        self.assistant_service.register_agent(assistant_agent)
        
        # For database_agent, we need to call it with customer_id
        db_agent = database_agent(self.customer_id)
        self.assistant_service.register_agent(db_agent)
        
        # Register other agents
        self.assistant_service.register_agent(internal_kb_agent)
        self.assistant_service.register_agent(web_search_agent)
        
        # Register root agent last (it needs to know about all other agents)
        # For root_assistant, it's a function that takes customer_id
        root_agent = root_assistant(self.customer_id)
        self.assistant_service.register_root_agent(root_agent)
        
        # Register tool functions with the kernel
        self.register_agent_tools_with_kernel()

    def register_agent_tools_with_kernel(self):
        """Register all agent tools with the kernel."""
        for agent_id, agent in self.assistant_service.agents.items():
            for tool in agent['tools']:
                # Create a closure to capture the tool name
                def create_tool_function(tool_name):
                    @kernel_function(name=tool_name, description=tool['description'])
                    async def tool_function(**kwargs):
                        # Call the tool and return the result
                        return await self.assistant_service.get_tool_response(tool_name, kwargs, None)
                    return tool_function
                
                # Add the function with the closure-captured tool name
                self.kernel.add_functions(
                    plugin_name=agent_id, 
                    functions=[create_tool_function(tool['name'])]
                )
            
            # Register agent switching functions
            if agent_id != "root":
                # Create a closure to capture the agent_id
                def create_switch_agent_function(agent_id):
                    @kernel_function(name=agent_id, description=agent['description'])
                    async def switch_agent(**kwargs):
                        # Notify that we're switching agents
                        self.dispatch_event("agent_switched", {"agent_id": agent_id})
                        # Return the agent ID to trigger agent switching
                        return agent_id
                    return switch_agent
                
                self.kernel.add_functions(
                    plugin_name="agents", 
                    functions=[create_switch_agent_function(agent_id)]
                )

    def on(self, event_name: str, callback: Callable):
        """Register a callback for a specific event."""
        if event_name in self.event_callbacks:
            self.event_callbacks[event_name].append(callback)

    def dispatch_event(self, event_name: str, data: Any):
        """Dispatch an event to all registered callbacks."""
        for callback in self.event_callbacks.get(event_name, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(data))
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    async def initialize(self):
        """Initialize the realtime agent."""
        # Get the root agent
        root_agent = self.assistant_service.get_agent("root")
        
        # Create execution settings with the root agent's system message and tools
        settings = AzureRealtimeExecutionSettings(
            instructions=root_agent["system_message"],
            voice="shimmer",  # Using shimmer as default voice
            turn_detection=TurnDetection(
                type="server_vad",
                create_response=True,
                silence_duration_ms=800,
                threshold=0.5
            ),
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
            tools=self.assistant_service.get_tools_for_assistant("root")
        )
        
        # Create the realtime agent with web-based audio handling
        self.realtime_agent = AzureRealtimeWebsocket(settings=settings)
        self.web_audio_handler = ChainlitWebAudioHandler(realtime_client=self.realtime_agent)
        
        return self

    async def add_audio_chunk(self, audio_chunk):
        """
        Add an audio chunk from the browser to the buffer
        and send it to the realtime agent.
        """
        if self.realtime_agent and audio_chunk:
            # Add to buffer for potential later use
            self._audio_buffer.extend(audio_chunk)
            
            # Send the audio chunk to the realtime agent
            await self.web_audio_handler.send_audio(audio_chunk)

    async def start(self):
        """Start the realtime conversation."""
        if not self.realtime_agent:
            await self.initialize()
        
        # Start the conversation
        async with self.web_audio_handler, self.realtime_agent(
            kernel=self.kernel,
            chat_history=self.chat_history,
            create_response=True,
        ):
            async for event in self.realtime_agent.receive(audio_output_callback=self.web_audio_handler.client_callback):
                await self.process_event(event)

    async def process_event(self, event):
        """Process events from the realtime agent."""
        # Process standard events
        if isinstance(event, RealtimeTextEvent):
            self.dispatch_event("text_received", {"text": event.text.text})
            
        elif isinstance(event, RealtimeAudioEvent):
            self.dispatch_event("audio_received", {"audio": event.audio})
        
        # Process service-specific events
        elif hasattr(event, "service_type"):
            match event.service_type:
                case ListenEvents.RESPONSE_CREATED:
                    # Start of a new response
                    self.dispatch_event("transcript_received", {"text": "", "is_start": True})
                
                case ListenEvents.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                    # Input transcript completed
                    if hasattr(event, "service_event") and "transcript" in event.service_event:
                        transcript = event.service_event["transcript"]
                        self.dispatch_event("transcript_received", {"text": transcript, "is_user": True})
                
                case ListenEvents.RESPONSE_OUTPUT_ITEM_DONE:
                    # Response completed
                    if hasattr(event, "service_event") and "item" in event.service_event:
                        item = event.service_event["item"]
                        self.dispatch_event("item_completed", {"item": item})
                        
                        # Check for function calls that indicate agent switching
                        if item.get("type") == "function_call" and item.get("status") == "completed":
                            # If the function name matches an agent ID, switch to that agent
                            if item.get("name") in self.assistant_service.agents:
                                agent_id = item.get("name")
                                agent = self.assistant_service.get_agent(agent_id)
                                
                                # Update session with new agent's settings
                                new_settings = AzureRealtimeExecutionSettings(
                                    instructions=agent["system_message"],
                                    turn_detection=TurnDetection(type="server_vad", create_response=True),
                                    tools=self.assistant_service.get_tools_for_assistant(agent_id)
                                )
                                
                                # Update the session
                                await self.realtime_agent.update_session(settings=new_settings)
                                
                                # Notify about agent switch
                                self.dispatch_event("agent_switched", {"agent_id": agent_id})
                
                case ListenEvents.ERROR:
                    # Handle errors
                    logger.error(f"Error in realtime agent: {event.service_event}")

    async def send_text_message(self, text: str):
        """Send a text message to the conversation."""
        if self.realtime_agent:
            # Add message to chat history
            self.chat_history.add_user_message(text)
            
            # Create a response
            await self.realtime_agent.create_response()

    async def stop(self):
        """Stop the conversation."""
        # Clean up resources
        if self.realtime_agent:
            # This will close the websocket connection
            await self.realtime_agent.__aexit__(None, None, None)
            self.realtime_agent = None
        
        if self.web_audio_handler:
            await self.web_audio_handler.__aexit__(None, None, None)
            self.web_audio_handler = None
            
        # Clear the audio buffer
        self._audio_buffer = bytearray()