import streamlit as st
import os
import sys
import logging
import json
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Check for Azure Cosmos DB availability
try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import common utilities
from utils import (
    setup_logging_and_monitoring, initialize_azure_clients,
    initialize_conversation, speech_to_text, text_to_speech,
    setup_sidebar_voice_controls, setup_sidebar_conversation_info,
    display_conversation_history, setup_page_header, setup_sidebar_header, setup_voice_input_recorder,
    setup_system_message_input, setup_voice_instruction_examples,
    create_chat_container, handle_audio_recording, initialize_session_messages,
    handle_chat_flow, ensure_fresh_conversation, add_message_to_session
)

# Import performance tracking
from utils.performance_metrics import PerformanceTracker, save_performance_metrics, analyze_customer_sentiment_from_conversation

# Import modular VoiceBot Classic components
from utils.voicebot_classic_config import (
    DEFAULT_SYSTEM_MESSAGE, DEFAULT_JSON_TEMPLATE, WELCOME_MESSAGE,
    CUSTOM_EXTRACTION_MESSAGE, MODEL_DESCRIPTIONS, DEFAULT_TEMPERATURE,
    DEFAULT_MODEL, DEFAULT_MAX_TOKENS, FINAL_RESPONSE_MAX_TOKENS
)
from utils.voicebot_classic_tools import get_available_tools
from utils.voicebot_classic_chat import VoiceBotClassicChat

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

# Initialize chat handler
if "chat_handler" not in st.session_state:
    st.session_state.chat_handler = VoiceBotClassicChat(
        client, conversation_manager, st.session_state.performance_tracker
    )

# Get all available model deployment names and set defaults
available_models = {}
try:
    available_models["gpt-4o"] = os.environ.get("AZURE_OPENAI_GPT4o_DEPLOYMENT")
    available_models["gpt-4o-mini"] = os.environ.get("AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT")
    available_models["gpt-4.1"] = os.environ.get("AZURE_OPENAI_GPT41_DEPLOYMENT")
    available_models["gpt-4.1-mini"] = os.environ.get("AZURE_OPENAI_GPT41_MINI_DEPLOYMENT")
    available_models["gpt-4.1-nano"] = os.environ.get("AZURE_OPENAI_GPT41_NANO_DEPLOYMENT")
    
    # Filter out None values (models not available)
    available_models = {k: v for k, v in available_models.items() if v is not None}
    
except Exception as e:
    logger.warning(f"Error loading models: {e}")
    # Fallback to just gpt-4o-mini if there's an issue
    available_models = {"gpt-4o-mini": os.environ.get("AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT", "gpt-4o-mini")}

# Default model deployment name (keeping backward compatibility)
gpt4omini = os.environ.get("AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT", "gpt-4o-mini")

def load_css(file_path):
    """Load CSS styles from file."""
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Create a wrapper function for the modular chat system
def basic_chat(user_request, conversation_history=None):
    """Wrapper function that uses the modular chat handler."""
    if conversation_history is None:
        conversation_history = []
    
    # Get settings from session state
    system_message = st.session_state.get("system_message", DEFAULT_SYSTEM_MESSAGE)
    json_template = st.session_state.get("json_template", "")
    selected_model_deployment = st.session_state.get("selected_model_deployment", gpt4omini)
    temperature = st.session_state.get("temperature", DEFAULT_TEMPERATURE)
    
    # Get available tools
    available_tools = get_available_tools(COSMOS_AVAILABLE)
    
    # Use the modular chat handler
    return st.session_state.chat_handler.basic_chat(
        user_request=user_request,
        conversation_history=conversation_history,
        system_message=system_message,
        json_template=json_template,
        selected_model_deployment=selected_model_deployment,
        temperature=temperature,
        available_tools=available_tools
    )
# Set up page header
setup_page_header("Azure OpenAI powered Self Service Chatbot")

# Initialize conversation on page load with voicebot type
initialize_conversation(conversation_manager, voicebot_type="classic")

# Set up sidebar configuration
setup_sidebar_header()

# Display available customers and their vehicles
def load_sample_customers():
    """Load sample customer data for display in sidebar."""
    customers_data = []
    assets_path = os.path.join(os.path.dirname(__file__), "..", "assets")
    
    try:
        # Load customer files
        customer_path = os.path.join(assets_path, "Cosmos_Customer")
        vehicle_path = os.path.join(assets_path, "Cosmos_Vehicles")
        
        if os.path.exists(customer_path) and os.path.exists(vehicle_path):
            # Get customer files
            customer_files = [f for f in os.listdir(customer_path) if f.endswith('.json')]
            vehicle_files = [f for f in os.listdir(vehicle_path) if f.endswith('.json')]
            
            for customer_file in customer_files:
                try:
                    with open(os.path.join(customer_path, customer_file), 'r', encoding='utf-8') as f:
                        customer_data = json.load(f)
                    
                    # Find matching vehicle file by customer_id
                    customer_id = customer_data.get("customer_id")
                    vehicle_data = None
                    
                    for vehicle_file in vehicle_files:
                        try:
                            with open(os.path.join(vehicle_path, vehicle_file), 'r', encoding='utf-8') as f:
                                temp_vehicle_data = json.load(f)
                            if temp_vehicle_data.get("customer_id") == customer_id:
                                vehicle_data = temp_vehicle_data
                                break
                        except Exception:
                            continue
                    
                    customers_data.append({
                        "name": f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}",
                        "plate": vehicle_data.get("license_plate", "N/A") if vehicle_data else "N/A",
                        "vehicles": vehicle_data.get("vehicles", []) if vehicle_data else []
                    })
                    
                except Exception as e:
                    logger.warning(f"Error loading customer file {customer_file}: {e}")
                    continue
                    
    except Exception as e:
        logger.warning(f"Error loading customer data: {e}")
    
    return customers_data

# Display customer information in sidebar
with st.sidebar:
    st.subheader("👥 Available Test Customers")
    
    sample_customers = load_sample_customers()
    
    if sample_customers:
        for customer in sample_customers:
            with st.expander(f"📋 {customer['name']}", expanded=False):
                st.write(f"**License Plate:** {customer['plate']}")
                
                if customer['vehicles']:
                    st.write("**Vehicles:**")
                    for i, vehicle in enumerate(customer['vehicles'], 1):
                        make = vehicle.get('make', 'Unknown')
                        model = vehicle.get('model', 'Unknown')
                        year = vehicle.get('year', 'Unknown')
                        color = vehicle.get('color', 'Unknown')
                        st.write(f"  {i}. {make} {model} ({year}, {color})")
                else:
                    st.write("No vehicle data available")
    else:
        st.info("No test customer data available")
    
    st.markdown("---")

# Voice controls - custom implementation with default TTS instructions
with st.sidebar:
    # Voice output toggle
    if "voice_on" not in st.session_state:
        st.session_state.voice_on = True
    st.session_state.voice_on = st.toggle(
        label="🔊 Enable Voice Output", 
        value=st.session_state.voice_on
    )
    
    # Voice selection
    available_voices = ["alloy", "ash", "ballad", "coral", "echo", "fable", 
                      "nova", "onyx", "sage", "shimmer"]
    if "selected_voice" not in st.session_state:
        st.session_state.selected_voice = "shimmer"
    st.session_state.selected_voice = st.selectbox(
        "🎤 Select Voice:",
        available_voices,
        index=available_voices.index(st.session_state.selected_voice)
    )
    
    # Set default TTS instructions without UI control
    if "tts_instructions" not in st.session_state:
        st.session_state.tts_instructions = "Speak with a professional, helpful tone."

voice_on = st.session_state.voice_on
selected_voice = st.session_state.selected_voice
tts_instructions = st.session_state.tts_instructions

# # Voice instruction examples
# setup_voice_instruction_examples()

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
    """Text-to-speech with performance tracking and better error handling."""
    st.session_state.performance_tracker.start_text_to_speech()
    try:
        logger.debug(f"TTS requested for text: '{text[:50]}...' (length: {len(text)})")
        result = text_to_speech(text, client)
        st.session_state.performance_tracker.end_text_to_speech()
        if result:
            logger.debug("TTS generation successful")
        else:
            logger.warning("TTS generation returned empty result")
        return result
    except Exception as e:
        st.session_state.performance_tracker.end_text_to_speech()
        logger.error(f"TTS generation failed: {e}")
        raise

# Add JSON template input to sidebar
with st.sidebar:
    # Set model to default value (gpt-4.1-mini) without UI control
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "gpt-4.1-mini"
    
    # Set the model deployment name
    if available_models and "gpt-4.1-mini" in available_models:
        st.session_state.selected_model_deployment = available_models["gpt-4.1-mini"]
    else:
        # Fallback to gpt4omini if gpt-4.1-mini is not available
        st.session_state.selected_model_deployment = gpt4omini
    
    # Set temperature to default value (0.0) without UI control
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.0
    
    # Add separator
    st.markdown("---")
    
    # Set system message to default value without UI control
    if "system_message" not in st.session_state:
        st.session_state.system_message = DEFAULT_SYSTEM_MESSAGE

    st.subheader("📋 JSON Template")
    if "json_template" not in st.session_state:
        st.session_state.json_template = DEFAULT_JSON_TEMPLATE
    
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
        # if test_model:
        #     st.info("🎯 Template ready for dynamic structured outputs")
        # else:
        #     st.error("❌ Template cannot be used for structured outputs")
            
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON format")
    except Exception as e:
        st.error(f"❌ Template error: {str(e)}")
    
    # # Add a small note about how the template is used
    # st.caption("This template will be dynamically converted to a Pydantic model for structured outputs.")
    # Finish Conversation section
    st.subheader("🏁 Finish Conversation")
    st.caption("Generate a structured JSON summary and save performance metrics.")
    
    if st.button("📋 Generate JSON Summary", type="primary"):
        # Set a flag to indicate we're generating summary (prevents message processing)
        st.session_state.generating_summary = True
        
        from utils.voicebot_common import generate_conversation_summary as shared_generate_summary
        
        # Get the selected model deployment name
        selected_model_deployment = st.session_state.get("selected_model_deployment", gpt4omini)
        
        # Analyze customer sentiment from conversation history
        if "messages" in st.session_state and st.session_state.messages:
            try:
                sentiment_score = analyze_customer_sentiment_from_conversation(
                    client, selected_model_deployment, st.session_state.messages
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
        
        # Generate the JSON summary with custom extraction message for location handling
        try:
            shared_generate_summary(client, selected_model_deployment, conversation_manager, st.session_state.json_template, CUSTOM_EXTRACTION_MESSAGE)
        except Exception as e:
            st.error(f"Error generating summary: {e}")
            logger.error(f"Summary generation failed: {e}")


# Handle audio recording
if custom_audio_bytes:
    handle_audio_recording(custom_audio_bytes, tracked_speech_to_text)

# Initialize session messages
initialize_session_messages()

# Welcome message setup - Auto-initiate conversation with welcome audio
# Add welcome message if conversation is empty and not already added
if len(st.session_state.messages) == 0 and "welcome_added" not in st.session_state:
    # Add welcome message to session
    add_message_to_session("assistant", WELCOME_MESSAGE)
    st.session_state.welcome_added = True
    
    # Auto-play welcome audio if voice is enabled
    if voice_on:
        try:
            audio_content = tracked_text_to_speech(WELCOME_MESSAGE)
            if audio_content:
                # Create a placeholder for the audio that will auto-play
                st.session_state.welcome_audio = audio_content
        except Exception as e:
            logger.error(f"Error generating welcome audio: {e}")

# Create conversation container
conversation_container = create_chat_container(600)

# Handle new message input
# Skip message processing if we're generating a summary
if st.session_state.get("generating_summary", False):
    # Clear the flag and don't process any messages
    st.session_state.generating_summary = False
    prompt = None
elif text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
elif "voice_prompt" in st.session_state:
    prompt = st.session_state.voice_prompt
    del st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        # Add user message
        add_message_to_session("user", prompt)
        
        # Display conversation history including the new user message
        display_conversation_history(st.session_state.messages)
        
        # Get and display assistant response with enhanced voice handling
        with st.chat_message("assistant"):
            with st.spinner("🤔 Processing your request..."):
                # Pass previous conversation history excluding system messages
                conversation_history = [msg for msg in st.session_state.messages if msg["role"] != "system"]
                response = basic_chat(prompt, conversation_history)
            
            # Display text response
            st.markdown(response)
            
            # Enhanced voice output handling
            if voice_on:
                try:
                    logger.debug(f"Voice enabled, processing TTS for response length: {len(response)}")
                    # Clean text for TTS
                    from utils.voicebot_common import cleanup_response_for_tts
                    audio_text = cleanup_response_for_tts(response)
                    logger.debug(f"Cleaned text for TTS: '{audio_text[:50]}...'")
                    
                    if audio_text.strip():  # Only proceed if there's text to speak
                        audio_content = tracked_text_to_speech(audio_text)
                        if audio_content:
                            logger.debug("Playing TTS audio")
                            st.audio(audio_content, format="audio/wav", autoplay=True)
                        else:
                            logger.warning("TTS returned no audio content")
                            st.warning("⚠️ Could not generate audio for this response")
                    else:
                        logger.warning("No text available for TTS after cleanup")
                        
                except Exception as e:
                    logger.error(f"Voice output error: {e}")
                    st.error(f"🔊 Audio generation failed: {str(e)}")
        
        # Add assistant response to session
        add_message_to_session("assistant", response)
    else:
        # Display existing conversation
        display_conversation_history(st.session_state.messages)
        
        # Auto-play welcome audio if it's available and hasn't been played yet
        if "welcome_audio" in st.session_state and "welcome_audio_played" not in st.session_state:
            st.audio(st.session_state.welcome_audio, format="audio/wav", autoplay=True)
            st.session_state.welcome_audio_played = True