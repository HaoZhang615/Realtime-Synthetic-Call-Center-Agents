import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
import json
import os
from typing import List, Dict
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
import util

from realtime2 import RealtimeClient
    
from agents.root import root_assistant
from agents.internal_kb import internal_kb_agent
from agents.database_agent import database_agent
from agents.assistant_agent import assistant_agent
from agents.web_search_agent import web_search_agent

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

async def setup_openai_realtime():
    """Instantiate and configure the OpenAI Realtime Client"""
    customer_id = cl.user_session.get("customer_id")
             
    openai_realtime = RealtimeClient(system_prompt = "")
    cl.user_session.set("track_id", str(uuid4()))
    async def handle_conversation_updated(event):
        item = event.get("item")
        delta = event.get("delta")
        """Currently used to stream audio back to the client."""
        if event:
            if "input_audio_transcription" in item["type"]:
                msg = cl.Message(content=delta["transcript"], author="user")
                msg.type = "user_message"
                await msg.send()
        if delta:
            if 'audio' in delta:
                audio = delta['audio']
                await cl.context.emitter.send_audio_chunk(cl.OutputAudioChunk(mimeType="pcm16", data=audio, track=cl.user_session.get("track_id")))
            if 'transcript' in delta:
                transcript = delta['transcript']
                pass
            if 'arguments' in delta:
                arguments = delta['arguments']
                pass
            
    async def handle_item_completed(item):
        """Used to populate the chat context with transcription once an item is completed."""
        if item["item"]["type"] == "message":
            content = item["item"]["content"][0]
            if content["type"] == "audio":
                await cl.Message(content=content["transcript"]).send()
    
    async def handle_conversation_interrupt(event):
        """Used to cancel the client previous audio playback."""
        cl.user_session.set("track_id", str(uuid4()))
        await cl.context.emitter.send_audio_interrupt()
        
    async def handle_error(event):
        logger.error(event)
    
    openai_realtime.on('conversation.updated', handle_conversation_updated)
    openai_realtime.on('conversation.item.completed', handle_item_completed)
    openai_realtime.on('conversation.interrupted', handle_conversation_interrupt)
    openai_realtime.on('error', handle_error)
    
    cl.user_session.set("openai_realtime", openai_realtime)
    
    # Agents must be registered before the root agent
    openai_realtime.assistant.register_agent(web_search_agent)
    openai_realtime.assistant.register_agent(internal_kb_agent)
    openai_realtime.assistant.register_agent(database_agent(customer_id))
    openai_realtime.assistant.register_agent(assistant_agent)
    openai_realtime.assistant.register_root_agent(root_assistant(customer_id))

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
        print(f"Customer ID: {customer_id}")
        cl.user_session.set("customer_id", customer_id)
        await cl.Message(content=f"Logged in successfully!").send()
        await setup_openai_realtime()
    else:
        await cl.Message(content="Login failed or timed out. Please refresh to try again.").send()

@cl.on_message
async def on_message(message: cl.Message):
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.send_user_message_content([{ "type": 'input_text', "text": message.content}])
    else:
        await cl.Message(content="Please activate voice mode before sending messages!").send()

@cl.on_audio_start
async def on_audio_start():
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        # TODO: might want to recreate items to restore context
        # openai_realtime.create_conversation_item(item)
        await openai_realtime.connect()
        logger.info("Connected to OpenAI realtime")
        return True
    except Exception as e:
        await cl.ErrorMessage(content=f"Failed to connect to OpenAI realtime: {e}").send()
        return False

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime:            
        if openai_realtime.is_connected():
            await openai_realtime.append_input_audio(chunk.data)
        else:
            logger.info("RealtimeClient is not connected")

@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.disconnect()