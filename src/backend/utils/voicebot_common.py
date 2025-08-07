"""
Common utilities for VoiceBot applications.
This module contains shared functions used across multiple VoiceBot implementations
to reduce code duplication and improve maintainability.
"""

import os
import logging
import hashlib
import streamlit as st
import io
from typing import Optional
from datetime import datetime
import pytz

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.monitor.opentelemetry import configure_azure_monitor

from utils import load_dotenv_from_azd
from utils.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)


def setup_logging_and_monitoring():
    """
    Configure logging and Azure monitoring with consistent settings.
    """
    logging.captureWarnings(True)
    logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO").upper())
    logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())
    
    if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
        configure_azure_monitor()
        logger.info("Azure Application Insights monitoring enabled")


def initialize_azure_clients():
    """
    Initialize Azure clients with proper authentication and configuration.
    
    Returns:
        tuple: (AzureOpenAI client, token_provider, conversation_manager)
    """
    try:
        # Load environment variables
        load_dotenv_from_azd()
        
        # Setup authentication
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        
        # Initialize Azure OpenAI client
        api_base = os.environ["AZURE_OPENAI_ENDPOINT"]
        api_version = "2025-03-01-preview"
        
        client = AzureOpenAI(
            azure_endpoint=api_base,
            azure_ad_token_provider=token_provider,
            api_version=api_version
        )
        
        # Initialize conversation manager
        try:
            conversation_manager = ConversationManager()
            logger.info("Conversation manager initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize conversation manager: {e}")
            conversation_manager = None
        
        logger.info("Azure clients initialized successfully")
        return client, token_provider, conversation_manager
        
    except Exception as e:
        logger.error(f"Failed to initialize Azure clients: {e}")
        raise


def get_session_id() -> str:
    """
    Generate a unique session ID for the current Streamlit session.
    
    Returns:
        str: Unique session identifier
    """
    if "session_id" not in st.session_state:
        session_data = str(st.session_state)
        st.session_state.session_id = hashlib.md5(session_data.encode()).hexdigest()[:16]
    return st.session_state.session_id


def get_customer_id() -> str:
    """
    Generate or get customer ID for conversation partitioning.
    In production, this would be the actual authenticated user ID.
    
    Returns:
        str: Customer identifier
    """
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = f"demo_user_{get_session_id()}"
    return st.session_state.customer_id


def initialize_conversation(conversation_manager: Optional[ConversationManager] = None):
    """
    Initialize or load conversation from Cosmos DB.
    
    Args:
        conversation_manager: Optional ConversationManager instance
    """
    if "conversation_doc" not in st.session_state and conversation_manager:
        try:
            customer_id = get_customer_id()
            session_id = get_session_id()
            
            st.session_state.conversation_doc = conversation_manager.create_conversation_document(
                customer_id=customer_id,
                session_id=session_id
            )
            
            logger.info(f"Initialized new conversation: {st.session_state.conversation_doc['id']}")
        except Exception as e:
            logger.error(f"Failed to initialize conversation: {e}")


def save_conversation_to_cosmos(conversation_manager: Optional[ConversationManager] = None):
    """
    Save current conversation to Cosmos DB.
    
    Args:
        conversation_manager: Optional ConversationManager instance
    """
    if conversation_manager and "conversation_doc" in st.session_state:
        try:
            success = conversation_manager.save_conversation(st.session_state.conversation_doc)
            if success:
                logger.debug("Conversation saved to Cosmos DB")
            else:
                logger.error("Failed to save conversation to Cosmos DB")
        except Exception as e:
            logger.error(f"Error saving conversation to Cosmos DB: {e}")


def speech_to_text(audio: bytes, client: AzureOpenAI) -> str:
    """
    Convert speech to text using Azure OpenAI.
    
    Args:
        audio: Audio bytes to transcribe
        client: AzureOpenAI client instance
        
    Returns:
        str: Transcribed text
    """
    try:
        transcribe_model = os.environ.get("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "gpt-4o-mini-transcribe")
        
        buffer = io.BytesIO(audio)
        buffer.name = "audio.wav"
        
        transcription_result = client.audio.transcriptions.create(
            file=buffer,
            model=transcribe_model,
            response_format="json"
        )
        
        buffer.close()
        return transcription_result.text
        
    except Exception as e:
        logger.error(f"Speech to text error: {e}")
        return "Sorry, I couldn't understand the audio."


def text_to_speech(text_input: str, client: AzureOpenAI) -> Optional[bytes]:
    """
    Convert text to speech using Azure OpenAI.
    
    Args:
        text_input: Text to convert to speech
        client: AzureOpenAI client instance
        
    Returns:
        Optional[bytes]: Audio content or None if error
    """
    try:
        tts_model = os.environ.get("AZURE_OPENAI_TTS_DEPLOYMENT", "gpt-4o-mini-tts")
        
        # Get voice settings from session state, with fallbacks
        voice = getattr(st.session_state, 'selected_voice', 'shimmer')
        instructions = getattr(st.session_state, 'tts_instructions', 'Speak with a professional, helpful tone.')
        
        response = client.audio.speech.create(
            model=tts_model,
            voice=voice,
            input=text_input,
            response_format="wav",
            instructions=instructions
        )
        
        return response.content
        
    except Exception as e:
        logger.error(f"Text to speech error: {e}")
        return None


def save_conversation_message(user_request: str, assistant_response: str, 
                            conversation_manager: Optional[ConversationManager] = None):
    """
    Save user and assistant messages to conversation in Cosmos DB.
    
    Args:
        user_request: User's message
        assistant_response: Assistant's response
        conversation_manager: Optional ConversationManager instance
    """
    if conversation_manager and "conversation_doc" in st.session_state:
        try:
            # Add user message
            conversation_manager.add_message_to_conversation(
                st.session_state.conversation_doc,
                role="user",
                content=user_request
            )
            
            # Add assistant response
            conversation_manager.add_message_to_conversation(
                st.session_state.conversation_doc,
                role="assistant",
                content=assistant_response
            )
            
            # Save to Cosmos DB
            save_conversation_to_cosmos(conversation_manager)
            
        except Exception as e:
            logger.error(f"Error saving conversation messages: {e}")


def setup_sidebar_voice_controls():
    """
    Set up common voice controls in the sidebar.
    
    Returns:
        tuple: (voice_on, selected_voice, tts_instructions)
    """
    with st.sidebar:
        # Voice output toggle
        if "voice_on" not in st.session_state:
            st.session_state.voice_on = False
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
        
        # TTS Instructions
        if "tts_instructions" not in st.session_state:
            st.session_state.tts_instructions = "Speak with a professional, helpful tone."
        st.session_state.tts_instructions = st.text_input(
            "🗣️ Voice Instructions:",
            value=st.session_state.tts_instructions,
            placeholder="Enter voice customization instructions...",
            help="Customize how the AI should speak (accent, tone, style, etc.)"
        )
        
        return st.session_state.voice_on, st.session_state.selected_voice, st.session_state.tts_instructions


def setup_sidebar_conversation_info():
    """
    Set up conversation info display in the sidebar.
    """
    with st.sidebar:
        st.subheader("💬 Conversation Info")
        if "conversation_doc" in st.session_state and st.session_state.conversation_doc:
            conv_doc = st.session_state.conversation_doc
            st.write(f"**Session:** `{conv_doc['session_id'][:8]}...`")
            st.write(f"**Messages:** {len(conv_doc['messages'])}")
            
            # Convert UTC to CET timezone
            try:
                created_utc = datetime.fromisoformat(conv_doc['created_at'].replace('Z', '+00:00'))
                cet = pytz.timezone('Europe/Zurich')
                created_cet = created_utc.astimezone(cet)
                st.write(f"**Created:** {created_cet.strftime('%H:%M:%S')} CET")
            except Exception:
                st.write(f"**Created:** {conv_doc.get('created_at', 'Unknown')}")
            
            # New conversation button
            if st.button("🔄 New Conversation"):
                # Clear session state for new conversation
                keys_to_clear = ["conversation_doc", "messages", "connected_agents", 
                               "agent_thread", "sk_orchestration", "sk_runtime"]
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.rerun()
        else:
            st.write("No active conversation")


def display_conversation_history(messages: list):
    """
    Display conversation history in the chat interface.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
    """
    for message in messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])


def process_audio_and_text_input():
    """
    Process both text and audio input from the user interface.
    
    Returns:
        Optional[str]: User prompt or None if no input
    """
    # Handle text input
    text_prompt = st.chat_input("Ask me anything!")
    
    # Handle audio input
    audio_prompt = None
    if "voice_prompt" in st.session_state:
        audio_prompt = st.session_state.voice_prompt
        del st.session_state.voice_prompt
    
    return text_prompt or audio_prompt


def cleanup_response_for_tts(text: str) -> str:
    """
    Clean up text response for text-to-speech conversion.
    
    Args:
        text: Raw text response
        
    Returns:
        str: Cleaned text suitable for TTS
    """
    import re
    
    # Remove text in parentheses (e.g., source references)
    cleaned = re.sub(r'\([^)]*\)', '', text)
    
    # Remove markdown formatting
    cleaned = re.sub(r'[*_`#]', '', cleaned)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


def get_default_system_message() -> str:
    """
    Get a default system message for VoiceBot applications.
    
    Returns:
        str: Default system message
    """
    return """You are a voice-based AI agent designed to assist with customer service and information requests. Your role is to interact with users in a natural, empathetic, and efficient manner. Your primary objectives are:

1. **Listen and Understand**: Carefully process user requests and ask clarifying questions when needed
2. **Provide Accurate Information**: Use available tools and knowledge to give helpful, accurate responses
3. **Maintain Professional Tone**: Be polite, clear, and concise in all interactions
4. **Handle Requests Efficiently**: Route complex requests to appropriate specialized agents when available

You must:
- Be polite, clear, and concise
- Ask follow-up questions if information is missing or unclear
- Handle interruptions or corrections gracefully
- Ensure conversations flow naturally while staying on task
- Provide structured responses when requested

If you cannot help with a specific request, politely explain your limitations and suggest alternative approaches."""
