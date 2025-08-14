"""
Chat functionality for VoiceBot Classic.
Contains the main chat logic and AI conversation handling.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class VoiceBotClassicChat:
    """Handles chat functionality for VoiceBot Classic."""
    
    def __init__(self, client, conversation_manager, performance_tracker):
        """
        Initialize the chat handler.
        
        Args:
            client: Azure OpenAI client
            conversation_manager: Conversation management utility
            performance_tracker: Performance tracking utility
        """
        self.client = client
        self.conversation_manager = conversation_manager
        self.performance_tracker = performance_tracker
    
    def get_current_datetime(self) -> str:
        """Get current datetime in a formatted string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    def save_conversation_message(self, user_request: str, assistant_response: str, tool_calls: Optional[List[Dict]] = None):
        """Save conversation message with tool calls to database."""
        try:
            # Import here to avoid circular imports
            from utils import save_conversation_message
            save_conversation_message(
                user_request, 
                assistant_response, 
                self.conversation_manager,
                tool_calls=tool_calls
            )
        except Exception as e:
            logger.error(f"Error saving conversation message: {e}")
    
    def process_tool_calls(self, tool_calls: List[Any], messages: List[Dict]) -> List[Dict]:
        """
        Process AI tool calls and return tool call logs.
        
        Args:
            tool_calls: List of tool calls from AI response
            messages: Conversation messages list to append to
            
        Returns:
            List of tool call logs for evaluation
        """
        tool_calls_log = []
        
        # Import tool functions here to avoid circular imports
        from utils.voicebot_classic_database import database_lookups
        from utils.voicebot_classic_email import send_email
        from utils.voicebot_classic_geolocation import get_geo_location
        
        for tool_call in tool_calls:
            function_result = None
            function_args = json.loads(tool_call.function.arguments)
            
            if tool_call.function.name == "send_email":
                function_result = send_email(function_args)
            elif tool_call.function.name == "database_lookups":
                function_result = database_lookups(function_args)
            elif tool_call.function.name == "get_geo_location":
                function_result = get_geo_location()

            # Ensure we always have a string result (matching working version behavior)
            if function_result is None:
                function_result = "Tool execution completed but no result was returned."
            
            # Log tool call for evaluation purposes (always log)
            tool_call_log = {
                "tool_call_id": tool_call.id,
                "function_name": tool_call.function.name,
                "function_arguments": function_args,
                "function_result": function_result,
                "timestamp": self.get_current_datetime(),
                "success": "error" not in str(function_result).lower()
            }
            tool_calls_log.append(tool_call_log)
            
            # Always add tool result to messages (matching working version)
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(function_result)
            }
            messages.append(tool_message)
        
        return tool_calls_log
    
    def basic_chat(self, user_request: str, conversation_history: Optional[List[Dict]] = None,
                   system_message: str = "", json_template: str = "", 
                   selected_model_deployment: str = "gpt-4o-mini", temperature: float = 0.7,
                   available_tools: List[Dict] = None) -> str:
        """
        Process a chat request with AI conversation handling.
        
        Args:
            user_request: User's input message
            conversation_history: Previous conversation messages
            system_message: System prompt for AI
            json_template: JSON template for structured outputs
            selected_model_deployment: AI model to use
            temperature: AI temperature setting
            available_tools: List of available AI tools
            
        Returns:
            AI assistant response
        """
        if conversation_history is None:
            conversation_history = []
        
        if available_tools is None:
            available_tools = []
            
        # Start tracking response latency
        self.performance_tracker.start_response_timing()
        self.performance_tracker.increment_message_count()
        
        # Add current datetime to the system message (invisible to user)
        system_message_with_datetime = f"Current date and time: {self.get_current_datetime()}\n\n{system_message}"
        
        # Update model parameters for tracking
        self.performance_tracker.update_model_parameters(temperature, system_message_with_datetime, selected_model_deployment)
        
        # Update system message with the current JSON template if needed
        if json_template:
            # Remove any existing JSON template section from the system message
            if "```json" in system_message_with_datetime:
                # Find start and end of the JSON template in the system message
                json_start = system_message_with_datetime.find("Use the following JSON template")
                if json_start > 0:
                    system_message_with_datetime = system_message_with_datetime[:json_start].strip()
            
            # Add the current JSON template
            system_message_with_datetime += f"\n\nUse the following JSON template for structured data collection:\n```json\n{json_template}\n```"
        
        messages = [
            {
                "role": "system",
                "content": system_message_with_datetime,
            }
        ]
        # Add previous conversation history
        messages.extend(conversation_history)
        # Add current user request
        messages.append({"role": "user", "content": user_request})
        
        try:
            response = self.client.chat.completions.create(
                model=selected_model_deployment,
                store=True,  # Store the response for performance tracking
                messages=messages,
                tools=available_tools if available_tools else None,
                tool_choice="auto" if available_tools else None,
                temperature=temperature,
                max_tokens=800,
            )
            
            # End response timing
            self.performance_tracker.end_response_timing()
            
            # Handle the response
            assistant_message = response.choices[0].message
            tool_calls_log = []  # For logging tool calls to CosmosDB
            
            # Check if the assistant wants to call a function
            if assistant_message.tool_calls:
                # Add the assistant message to conversation history
                messages.append(assistant_message)
                
                # Process tool calls
                tool_calls_log = self.process_tool_calls(assistant_message.tool_calls, messages)
                
                # Get final response after tool execution
                final_response = self.client.chat.completions.create(
                    model=selected_model_deployment,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=4000,
                )
                
                assistant_response = final_response.choices[0].message.content
            else:
                assistant_response = assistant_message.content
            
            # Save conversation to Cosmos DB using common utility with tool calls
            self.save_conversation_message(
                user_request, 
                assistant_response, 
                tool_calls=tool_calls_log if tool_calls_log else None
            )
            
            return assistant_response
            
        except Exception as e:
            self.performance_tracker.end_response_timing()
            logger.error(f"Error in basic_chat: {e}")
            raise
