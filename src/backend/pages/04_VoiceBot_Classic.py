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

# Add JSON template input to sidebar
with st.sidebar:
    # Model selection
    st.subheader("🤖 Model Selection")
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL
    
    # Create dropdown for model selection
    if available_models:
        st.session_state.selected_model = st.selectbox(
            "Choose AI Model:",
            options=list(available_models.keys()),
            index=list(available_models.keys()).index(st.session_state.selected_model) 
                  if st.session_state.selected_model in available_models else 0,
            help="Select the AI model to use for conversation"
        )
        
        # Store the deployment name for the selected model
        st.session_state.selected_model_deployment = available_models[st.session_state.selected_model]
        
        # Show model description
        if st.session_state.selected_model in MODEL_DESCRIPTIONS:
            st.caption(MODEL_DESCRIPTIONS[st.session_state.selected_model])
            
        st.info(f"Using deployment: `{st.session_state.selected_model_deployment}`")
    else:
        st.error("No models available. Check environment configuration.")
        st.session_state.selected_model_deployment = gpt4omini
    
    # Temperature control
    st.subheader("🎛️ Model Settings")
    if "temperature" not in st.session_state:
        st.session_state.temperature = DEFAULT_TEMPERATURE
    
    st.session_state.temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.temperature,
        step=0.1,
        help="Controls randomness: 0.0 = deterministic, 1.0 = very creative"
    )
    
    
    # Add separator
    st.markdown("---")
    
    system_message = setup_system_message_input(DEFAULT_SYSTEM_MESSAGE)

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
        # Use the common chat flow handler with tracked TTS
        handle_chat_flow(prompt, basic_chat, voice_on, tracked_text_to_speech)
    else:
        # Display existing conversation
        display_conversation_history(st.session_state.messages)
        
        # Auto-play welcome audio if it's available and hasn't been played yet
        if "welcome_audio" in st.session_state and "welcome_audio_played" not in st.session_state:
            st.audio(st.session_state.welcome_audio, format="audio/wav", autoplay=True)
            st.session_state.welcome_audio_played = True