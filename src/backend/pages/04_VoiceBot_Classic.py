import streamlit as st
import os
import sys
import logging
import re
from datetime import datetime
import pytz

from audio_recorder_streamlit import audio_recorder

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import common utilities
from utils import (
    setup_logging_and_monitoring, initialize_azure_clients, get_session_id,
    get_customer_id, initialize_conversation, save_conversation_to_cosmos,
    speech_to_text, text_to_speech, save_conversation_message,
    setup_sidebar_voice_controls, setup_sidebar_conversation_info,
    display_conversation_history, cleanup_response_for_tts, get_default_system_message,
    setup_page_header, setup_sidebar_header, setup_voice_input_recorder,
    setup_system_message_input, setup_voice_instruction_examples,
    create_chat_container, handle_audio_recording, initialize_session_messages,
    add_message_to_session, handle_chat_flow
)

# Configure logging and monitoring
setup_logging_and_monitoring()

logger = logging.getLogger(__name__)
logger.debug("Starting VoiceBot Classic page")

# Initialize Azure clients
client, token_provider, conversation_manager = initialize_azure_clients()

# Get model deployment names
gpt4omini = os.environ["AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT"]

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Basic chat function without web search or customer data
def basic_chat(user_request, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
        
    # Use the system message from session state
    system_message = st.session_state.system_message
    
    messages = [
        {
            "role": "system",
            "content": system_message,
        }
    ]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_request})
    
    response = client.chat.completions.create(
        model=gpt4omini,
        messages=messages,
        temperature=0.7,
        max_tokens=800,
    )
    
    assistant_response = response.choices[0].message.content
    
    # Save conversation to Cosmos DB using common utility
    save_conversation_message(user_request, assistant_response, conversation_manager)
    
    return assistant_response
# Set up page header
setup_page_header("Azure OpenAI powered Self Service Chatbot")

# Initialize conversation on page load
initialize_conversation(conversation_manager)

# Set up sidebar configuration
setup_sidebar_header()

# Voice controls
voice_on, selected_voice, tts_instructions = setup_sidebar_voice_controls()

# System message configuration
default_system_message = """You are a voice-based AI agent designed to assist Mobi 24 with car insurance claims handling. Your role is to interact with customers over the phone in a natural, empathetic, and efficient manner. Your primary objectives are:

Gather Information: Ask relevant questions to collect all necessary details about the car insurance claim, including:

Personal and contact information of the caller
Vehicle details (make, model, registration number)
Incident details (date, time, location, description of the event)
Involvement of third parties or injuries
Immediate assistance needs (e.g. towing, roadside help)
Confirm Completeness: Summarise the collected information and confirm with the caller that all details are correct and complete.

Output Structured Data: At the end of the call, generate a structured JSON object containing all the collected information, clearly labelled and ready for downstream processing by a human validator or automated system.

You must:

Be polite, clear, and concise.
Ask follow-up questions if information is missing or unclear.
Handle interruptions or corrections gracefully.
Ensure the conversation flows naturally while staying on task.
Do not make assumptions or provide legal or policy advice. If the caller asks something outside your scope, politely redirect them to a human agent."""

system_message = setup_system_message_input(default_system_message)

# Voice instruction examples
setup_voice_instruction_examples()

# Conversation info
setup_sidebar_conversation_info()

# Voice input recorder
custom_audio_bytes = setup_voice_input_recorder()

# Handle audio recording
if custom_audio_bytes:
    handle_audio_recording(custom_audio_bytes, lambda audio: speech_to_text(audio, client))

# Initialize session messages
initialize_session_messages()

# Create conversation container
conversation_container = create_chat_container(600)

# Handle new message input
if text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
elif "voice_prompt" in st.session_state:
    prompt = st.session_state.voice_prompt
    del st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        # Use the common chat flow handler
        def tts_func(text):
            return text_to_speech(text, client)
        
        handle_chat_flow(prompt, basic_chat, voice_on, tts_func)
    else:
        # Display existing conversation
        display_conversation_history(st.session_state.messages)