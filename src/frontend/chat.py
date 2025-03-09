import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
import json
import os
import asyncio
from typing import List, Dict
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
import util

from semantic_kernel_realtime import RealtimeConversationHandler
    
def load_customers() -> List[Dict]:
    util.load_dotenv_from_azd()
    credential = DefaultAzureCredential()
    cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
    cosmos_client = CosmosClient(cosmos_endpoint, credential)
    database_name = os.getenv("COSMOSDB_DATABASE")
    customer_container_name = "Customer"
    
    try:
        database = cosmos_client.get_database_client(database_name)
        container = database.get_container_client(customer_container_name)
        
        # Query all customers
        query = "SELECT c.customer_id, c.first_name, c.last_name FROM c"
        items = list(container.query_items(query, enable_cross_partition_query=True))
        
        return [{
            'id': item['customer_id'],  # Using customer_id as id for consistency
            'name': f"{item['first_name']} {item['last_name']}"
        } for item in items]
    except exceptions.CosmosResourceNotFoundError as e:
        logger.error(f"CosmosHttpResponseError: {e}")
        return []

async def setup_conversation_handler():
    """Instantiate and configure the Semantic Kernel Realtime Conversation Handler"""
    customer_id = cl.user_session.get("customer_id")
    
    # Create the conversation handler
    conversation_handler = RealtimeConversationHandler(customer_id=customer_id)
    cl.user_session.set("track_id", str(uuid4()))
    
    # Register event handlers
    async def handle_text_received(event):
        """Handle text deltas from the assistant"""
        text = event.get("text")
        if text:
            # We only append to the message if it exists, otherwise create a new one
            current_message = cl.user_session.get("current_assistant_message")
            if current_message:
                await current_message.stream_token(text)
            else:
                new_message = cl.Message(content=text, author="Assistant")
                await new_message.send()
                cl.user_session.set("current_assistant_message", new_message)
    
    async def handle_transcript_received(event):
        """Handle transcript events"""
        text = event.get("text")
        is_user = event.get("is_user", False)
        is_start = event.get("is_start", False)
        
        if is_start:
            # When a new response starts, reset the current assistant message
            cl.user_session.set("current_assistant_message", None)
        elif is_user and text:
            # Show user transcript
            msg = cl.Message(content=text, author="user")
            msg.type = "user_message"
            await msg.send()
    
    async def handle_audio_received(event):
        """Handle audio deltas from the assistant"""
        audio = event.get("audio")
        if audio and hasattr(audio, "data"):
            # Send audio chunk to the client
            await cl.context.emitter.send_audio_chunk(
                cl.OutputAudioChunk(
                    mimeType="pcm16",
                    data=audio.data, 
                    track=cl.user_session.get("track_id")
                )
            )
    
    async def handle_agent_switched(event):
        """Handle agent switching events"""
        agent_id = event.get("agent_id")
        if agent_id:
            # Notify the user that we're switching agents
            await cl.Message(
                content=f"_Switching to {agent_id} agent..._",
                author="System"
            ).send()
            
            # Reset current message when switching agents
            cl.user_session.set("current_assistant_message", None)
    
    # Register all event handlers
    conversation_handler.on("text_received", handle_text_received)
    conversation_handler.on("transcript_received", handle_transcript_received)
    conversation_handler.on("audio_received", handle_audio_received)
    conversation_handler.on("agent_switched", handle_agent_switched)
    
    # Store in user session
    cl.user_session.set("conversation_handler", conversation_handler)
    
    # Initialize the conversation handler
    await conversation_handler.initialize()
    
    return conversation_handler

@cl.on_chat_start
async def start():
    # Load customer list
    customers = load_customers()
    
    # Create customer selection dropdown
    res = await cl.AskActionMessage(
        content="Please select a customer to login:",
        actions=[
            cl.Action(
                name="login",
                value=str(customer['id']),
                label=customer['name'],
                payload={"customer_id": customer['id']}
            )
            for customer in customers
        ],
    ).send()
    
    if res:
        # Get customer_id from the payload
        customer_id = res['payload']['customer_id']
        logger.info(f"Customer ID: {customer_id}")
        cl.user_session.set("customer_id", customer_id)
        await cl.Message(content=f"Logged in successfully!").send()
        
        # Setup the conversation handler with the selected customer
        await setup_conversation_handler()
    else:
        await cl.Message(content="Login failed or timed out. Please refresh to try again.").send()

@cl.on_message
async def on_message(message: cl.Message):
    conversation_handler = cl.user_session.get("conversation_handler")
    if conversation_handler:
        # Send text message to the conversation
        await conversation_handler.send_text_message(message.content)
    else:
        await cl.Message(content="Please activate voice mode before sending messages!").send()

@cl.on_audio_start
async def on_audio_start():
    try:
        conversation_handler = cl.user_session.get("conversation_handler")
        if not conversation_handler:
            conversation_handler = await setup_conversation_handler()
        
        # Start the conversation handler in a background task
        task = asyncio.create_task(conversation_handler.start())
        cl.user_session.set("conversation_task", task)
        logger.info("Started Semantic Kernel realtime conversation")
        return True
    except Exception as e:
        logger.error(f"Failed to start conversation: {e}")
        await cl.ErrorMessage(content=f"Failed to connect to realtime service: {e}").send()
        return False

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    conversation_handler = cl.user_session.get("conversation_handler")
    if conversation_handler:
        # Send the audio chunk directly to our conversation handler
        await conversation_handler.add_audio_chunk(chunk.data)
    else:
        logger.warning("Audio chunk received but no conversation handler available")

@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    conversation_handler = cl.user_session.get("conversation_handler")
    conversation_task = cl.user_session.get("conversation_task")
    
    if conversation_task and not conversation_task.done():
        conversation_task.cancel()
        try:
            await conversation_task
        except asyncio.CancelledError:
            pass
    
    if conversation_handler:
        await conversation_handler.stop()