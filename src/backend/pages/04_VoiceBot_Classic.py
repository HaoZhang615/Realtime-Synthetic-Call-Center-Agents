import streamlit as st
import os
import sys
import logging
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import common utilities
from utils import (
    setup_logging_and_monitoring, initialize_azure_clients,
    initialize_conversation, speech_to_text, text_to_speech, save_conversation_message,
    setup_sidebar_voice_controls,setup_sidebar_conversation_info,
    display_conversation_history, setup_page_header, setup_sidebar_header, setup_voice_input_recorder,
    setup_system_message_input, setup_voice_instruction_examples,
    create_chat_container, handle_audio_recording, initialize_session_messages,
    handle_chat_flow, ensure_fresh_conversation, get_current_datetime
)

# Import performance tracking
from utils.performance_metrics import PerformanceTracker, save_performance_metrics, analyze_customer_sentiment_from_conversation

# Configure logging and monitoring
setup_logging_and_monitoring()

logger = logging.getLogger(__name__)
logger.debug("Starting VoiceBot Classic page")

# Initialize Azure clients
client, token_provider, conversation_manager = initialize_azure_clients()

# Ensure a fresh conversation for this page (resets if coming from a different page)
ensure_fresh_conversation("04")

# Initialize performance tracker
if "performance_tracker" not in st.session_state:
    st.session_state.performance_tracker = PerformanceTracker()
    st.session_state.performance_tracker.start_session()

# Get model deployment names
gpt4omini = os.environ["AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT"]

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Removed local JSON schema + summary functions now centralized in voicebot_common

# Basic chat function without web search or customer data
def basic_chat(user_request, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
        
    # Start tracking response latency
    st.session_state.performance_tracker.start_response_timing()
    st.session_state.performance_tracker.increment_message_count()
        
    # Use the system message from session state
    system_message = st.session_state.system_message
    
    # Add current datetime to the system message (invisible to user)
    system_message_with_datetime = f"Current date and time: {get_current_datetime()}\n\n{system_message}"
    
    # Update model parameters for tracking
    temperature = st.session_state.get("temperature", 0.7)
    st.session_state.performance_tracker.update_model_parameters(temperature, system_message_with_datetime, gpt4omini)
    
    # Update system message with the current JSON template if needed
    if "json_template" in st.session_state and st.session_state.json_template:
        # Remove any existing JSON template section from the system message
        if "```json" in system_message_with_datetime:
            # Find start and end of the JSON template in the system message
            json_start = system_message_with_datetime.find("Use the following JSON template")
            if json_start > 0:
                system_message_with_datetime = system_message_with_datetime[:json_start].strip()
        
        # Add the current JSON template
        system_message_with_datetime += f"\n\nUse the following JSON template for structured data collection:\n```json\n{st.session_state.json_template}\n```"
    
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
        response = client.chat.completions.create(
            model=gpt4omini,
            messages=messages,
            temperature=temperature,
            max_tokens=800,
        )
        
        # End response timing
        st.session_state.performance_tracker.end_response_timing()
        
        assistant_response = response.choices[0].message.content
        
        # Save conversation to Cosmos DB using common utility
        save_conversation_message(user_request, assistant_response, conversation_manager)
        
        return assistant_response
        
    except Exception as e:
        st.session_state.performance_tracker.end_response_timing()
        logger.error(f"Error in basic_chat: {e}")
        raise
# Set up page header
setup_page_header("Azure OpenAI powered Self Service Chatbot")

# Initialize conversation on page load
initialize_conversation(conversation_manager)

# Set up sidebar configuration
setup_sidebar_header()

# Voice controls
voice_on, selected_voice, tts_instructions = setup_sidebar_voice_controls()

# Voice instruction examples
setup_voice_instruction_examples()

setup_sidebar_conversation_info()

# Voice input recorder
custom_audio_bytes = setup_voice_input_recorder()

# Wrapper functions for performance tracking
def tracked_speech_to_text(audio_bytes):
    """Speech-to-text with performance tracking."""
    st.session_state.performance_tracker.start_speech_to_text()
    try:
        result = speech_to_text(audio_bytes, client)
        st.session_state.performance_tracker.end_speech_to_text()
        return result
    except Exception as e:
        st.session_state.performance_tracker.end_speech_to_text()
        raise

def tracked_text_to_speech(text):
    """Text-to-speech with performance tracking."""
    st.session_state.performance_tracker.start_text_to_speech()
    try:
        result = text_to_speech(text, client)
        st.session_state.performance_tracker.end_text_to_speech()
        return result
    except Exception as e:
        st.session_state.performance_tracker.end_text_to_speech()
        raise

# Default JSON template for structured data collection
default_json_template = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Car Insurance Claim",
  "type": "object",
  "properties": {
    "personalInfo": {
      "type": "object",
      "properties": {
        "fullName": { "type": "string" },
        "phoneNumber": { "type": "string" },
        "email": { "type": "string", "format": "email" },
        "policyNumber": { "type": "string" }
      },
      "required": ["fullName"],
      "anyOf": [
        { "required": ["phoneNumber"] },
        { "required": ["email"] }
      ]
    },
    "vehicleInfo": {
      "type": "object",
      "properties": {
        "make": { "type": "string" },
        "model": { "type": "string" },
        "year": { "type": "integer", "minimum": 1886 },
        "registrationNumber": { "type": "string" },
        "vin": { "type": "string" }
      },
      "required": ["make", "model", "year"],
      "anyOf": [
        { "required": ["registrationNumber"] },
        { "required": ["vin"] }
      ]
    },
    "incidentInfo": {
      "type": "object",
      "properties": {
        "date": { "type": "string", "format": "date" },
        "time": { "type": "string", "format": "time" },
        "location": { "type": "string" },
        "description": { "type": "string" },
        "thirdPartyInvolved": { "type": "boolean" },
        "injuries": { "type": "boolean" }
      },
      "required": ["date", "location", "description"]
    },
    "supportingDocuments": {
      "type": "object",
      "properties": {
        "photos": { "type": "array", "items": { "type": "string" } },
        "policeReport": { "type": "string" },
        "repairBills": { "type": "array", "items": { "type": "string" } }
      },
      "required": []
    },
    "assistanceNeeded": {
      "type": "object",
      "properties": {
        "towing": { "type": "boolean" },
        "rentalCar": { "type": "boolean" },
        "repairs": { "type": "boolean" },
        "other": { "type": "string" }
      },
      "required": []
    }
  },
  "required": ["personalInfo", "vehicleInfo", "incidentInfo"]
}
"""
# System message configuration
default_system_message = """You are a voice-based AI agent designed to assist Mobi 24 with car insurance claims handling. Your role is to interact with customers over the phone in a natural, empathetic, and efficient manner.

YOUR PRIMARY OBJECTIVES:

1. GATHER INFORMATION STRATEGICALLY:
   - First determine the nature of the customer's issue to guide your information collection
   - REQUIRED INFORMATION: Identify and collect all fields marked as "required" in the JSON template
   - OPTIONAL INFORMATION: Only ask for optional fields when relevant to the customer's specific situation
   - Adapt your questions based on the conversation context and urgency of the situation

2. STRUCTURE YOUR CONVERSATION:
   - Begin with an empathetic greeting and determine the reason for contact
   - For emergency situations (accident with injuries, stranded vehicles), prioritize immediate assistance needs
   - For standard claims, collect information in a logical order: personal → vehicle → incident → assistance
   - Group related questions together to make the conversation flow naturally
   - Confirm critical information before moving to the next section

3. CONFIRM COMPLETENESS:
   - Summarize the key information you've collected to verify accuracy
   - Give the customer an opportunity to add or correct details
   - Ensure all required fields from the JSON template have values

CONVERSATIONAL GUIDELINES:

- Be polite, clear, and concise
- Ask follow-up questions if information is missing or unclear
- Handle interruptions or corrections gracefully
- Use a natural conversation flow while staying on task
- For emergency situations, be efficient but calm and reassuring
- Explain why you need certain information to increase customer comfort
- Do not make assumptions or provide legal/policy advice
- If asked something outside your scope, politely redirect to a human agent

When using the JSON template:
- Pay attention to the "required" fields - these must be collected
- Use the structure of the template to guide your questioning sequence
- Only collect optional information that's relevant to the specific claim circumstance"""

# Add JSON template input to sidebar
with st.sidebar:
    # Temperature control
    st.subheader("🎛️ Model Settings")
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.7
    
    st.session_state.temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.temperature,
        step=0.1,
        help="Controls randomness: 0.0 = deterministic, 1.0 = very creative"
    )
    st.subheader("📋 JSON Template")
    if "json_template" not in st.session_state:
        st.session_state.json_template = default_json_template
    
    st.session_state.json_template = st.text_area(
        "Structured Data Template:",
        value=st.session_state.json_template,
        height=300,
        help="This JSON template will be used to structure the data collected during the conversation."
    )
    
    # Validate the JSON template and show status
    try:
        json.loads(st.session_state.json_template)
        st.success("✅ Valid JSON template")
        
        # Test dynamic model creation
        # Attempt dynamic model creation using shared utility
        from utils.voicebot_common import create_dynamic_pydantic_model, generate_conversation_summary as shared_generate_summary
        test_model = create_dynamic_pydantic_model(st.session_state.json_template)
        if test_model:
            st.info("🎯 Template ready for dynamic structured outputs")
        else:
            st.error("❌ Template cannot be used for structured outputs")
            
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON format")
    except Exception as e:
        st.error(f"❌ Template error: {str(e)}")
    
    # Add a small note about how the template is used
    st.caption("This template will be dynamically converted to a Pydantic model for structured outputs.")
    
    
    # Add separator
    st.markdown("---")
    system_message = setup_system_message_input(default_system_message)

    # Finish Conversation section
    st.subheader("🏁 Finish Conversation")
    st.caption("Generate a structured JSON summary and save performance metrics.")
    
    if st.button("📋 Generate JSON Summary", type="primary"):
        from utils.voicebot_common import generate_conversation_summary as shared_generate_summary
        
        # Analyze customer sentiment from conversation history
        if "messages" in st.session_state and st.session_state.messages:
            try:
                sentiment_score = analyze_customer_sentiment_from_conversation(
                    client, gpt4omini, st.session_state.messages
                )
                st.session_state.performance_tracker.set_customer_sentiment(sentiment_score)
                st.success(f"Customer sentiment analyzed: {sentiment_score}/5")
            except Exception as e:
                logger.error(f"Error analyzing sentiment: {e}")
                st.warning("Could not analyze customer sentiment")
        
        # End session tracking
        st.session_state.performance_tracker.end_session()
        
        # Save performance metrics to conversation document
        if "conversation_doc" in st.session_state and st.session_state.conversation_doc:
            logger.info(f"Saving performance metrics to conversation: {st.session_state.conversation_doc.get('id', 'unknown')}")
            save_performance_metrics(st.session_state.conversation_doc, st.session_state.performance_tracker)
            logger.info(f"Performance metrics saved. Document keys: {list(st.session_state.conversation_doc.keys())}")
            
            # Save updated conversation with metrics to CosmosDB
            try:
                conversation_manager.save_conversation(st.session_state.conversation_doc)
                st.success("Performance metrics saved to CosmosDB")
                logger.info("Successfully saved conversation with metrics to CosmosDB")
            except Exception as e:
                logger.error(f"Error saving conversation with metrics: {e}")
                st.error("Could not save performance metrics")
        else:
            logger.warning("No conversation document found to save metrics")
            st.warning("No conversation document found to save metrics")
        
        # Generate the JSON summary
        shared_generate_summary(client, gpt4omini, conversation_manager, st.session_state.json_template)


# Handle audio recording
if custom_audio_bytes:
    handle_audio_recording(custom_audio_bytes, tracked_speech_to_text)

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
        # Use the common chat flow handler with tracked TTS
        handle_chat_flow(prompt, basic_chat, voice_on, tracked_text_to_speech)
    else:
        # Display existing conversation
        display_conversation_history(st.session_state.messages)