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
import json
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
import pytz
from pydantic import BaseModel, create_model

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


def get_current_datetime() -> str:
    """
    Get the current date and time in a formatted string.
    
    Returns:
        str: Current date and time formatted as "YYYY-MM-DD HH:MM:SS UTC"
    """
    current_time = datetime.now(timezone.utc)
    return current_time.strftime("%Y-%m-%d %H:%M:%S UTC")


def initialize_conversation(conversation_manager: Optional[ConversationManager] = None, voicebot_type: Optional[str] = None):
    """
    Initialize or load conversation from Cosmos DB.
    
    Args:
        conversation_manager: Optional ConversationManager instance
        voicebot_type: Optional voicebot type identifier (e.g., "classic", "multiagent")
    """
    if "conversation_doc" not in st.session_state and conversation_manager:
        try:
            customer_id = get_customer_id()
            session_id = get_session_id()
            
            st.session_state.conversation_doc = conversation_manager.create_conversation_document(
                customer_id=customer_id,
                session_id=session_id,
                voicebot_type=voicebot_type
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
        return "Something is wrong with the audio conversion."


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
                            conversation_manager: Optional[ConversationManager] = None,
                            tool_calls: Optional[List[Dict]] = None):
    """
    Save user and assistant messages to conversation in Cosmos DB.
    
    Args:
        user_request: User's message
        assistant_response: Assistant's response
        conversation_manager: Optional ConversationManager instance
        tool_calls: Optional list of tool call information for evaluation
    """
    if conversation_manager and "conversation_doc" in st.session_state:
        try:
            # Add user message
            conversation_manager.add_message_to_conversation(
                st.session_state.conversation_doc,
                role="user",
                content=user_request
            )
            
            # Add assistant response (with tool calls if present)
            conversation_manager.add_message_to_conversation(
                st.session_state.conversation_doc,
                role="assistant",
                content=assistant_response,
                tool_calls=tool_calls
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
        # New conversation button
        if st.button("🔄 New Conversation"):
            # Clear session state for new conversation
            keys_to_clear = ["conversation_doc", "messages", "connected_agents", 
                            "agent_thread"]
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

def ensure_fresh_conversation(page_id: str):
    """Ensure a fresh conversation session when navigating between pages.

    If the user switches from one voice bot page to another (e.g., 04 -> 05),
    we clear conversation-related session_state so each page starts its own
    independent session and history.

    Args:
        page_id: A short identifier for the page (e.g., "04", "05").
    """
    current_page = st.session_state.get("active_conversation_page")
    if current_page != page_id:
        # Keys that define/hold a conversation context
        keys_to_clear = [
            "conversation_doc",
            "messages",
            "connected_agents",
            "agent_thread",
        ]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state.active_conversation_page = page_id
        logger.info(f"Started new conversation session for page {page_id}")
    else:
        # Same page reload; keep conversation
        logger.debug(f"Retaining existing conversation for page {page_id}")


# ---------------------- Dynamic Schema & Summary Utilities ---------------------- #

def json_schema_to_pydantic_type(schema_def: Dict[str, Any], field_name: str = "DynamicField"):
    """Convert a JSON schema field definition into a Pydantic type annotation.

    Supports basic JSON schema types: string, integer, number, boolean, array, object.
    Nested objects produce nested dynamic Pydantic models.
    """
    schema_type = schema_def.get("type")

    if schema_type == "string":
        return (Optional[str], None)
    if schema_type == "integer":
        return (Optional[int], None)
    if schema_type == "number":
        return (Optional[float], None)
    if schema_type == "boolean":
        return (Optional[bool], None)
    if schema_type == "array":
        items_schema = schema_def.get("items", {})
        if items_schema.get("type") == "string":
            return (Optional[List[str]], None)
        return (Optional[List[Any]], None)
    if schema_type == "object":
        properties = schema_def.get("properties", {})
        nested_fields = {}
        for prop_name, prop_schema in properties.items():
            prop_type, _ = json_schema_to_pydantic_type(prop_schema, prop_name)
            nested_fields[prop_name] = prop_type
        nested_model = create_model(f"{field_name}Model", **nested_fields)
        return (Optional[nested_model], None)
    # Fallback
    return (Optional[Any], None)


def create_dynamic_pydantic_model(json_template: str) -> Optional[BaseModel]:
    """Create a dynamic Pydantic model from a JSON schema template string.

    Returns the generated model class or None on error. Errors are surfaced to the UI.
    """
    try:
        schema = json.loads(json_template)
        properties = schema.get("properties", {})
        fields = {}
        for field_name, field_schema in properties.items():
            field_type, _ = json_schema_to_pydantic_type(field_schema, field_name)
            fields[field_name] = field_type
        DynamicModel = create_model("DynamicClaimModel", **fields)
        return DynamicModel
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON template: {e}")
    except Exception as e:
        st.error(f"Error creating dynamic model: {e}")
        logger.error(f"create_dynamic_pydantic_model error: {e}")
    return None


def generate_conversation_summary(client: AzureOpenAI, model_name: str, conversation_manager: Optional[ConversationManager], json_template: str,
                                   extraction_system_message: str = "You are a data extraction expert specializing in extracting structured information from conversations. Extract information accurately and use null for any missing information.") -> Optional[Dict[str, Any]]:
    """Generate a structured JSON summary for the active conversation using dynamic structured outputs.

    Args:
        client: AzureOpenAI client
        model_name: Deployment name to use for structured output parsing
        conversation_manager: ConversationManager instance
        json_template: JSON schema template string
        extraction_system_message: System prompt for extraction

    Returns:
        Parsed dictionary of extracted structured data or None on failure.
    """
    try:
        if not conversation_manager:
            st.error("Conversation manager not available.")
            return None
        if "conversation_doc" not in st.session_state or not st.session_state.conversation_doc:
            st.error("No active conversation found.")
            return None
        conversation_doc = st.session_state.conversation_doc

        # Build plain-text transcript
        conversation_text_lines = []
        for message in conversation_doc.get("messages", []):
            role = message.get("role", "")
            content = message.get("content", "")
            conversation_text_lines.append(f"{role.upper()}: {content}")
        conversation_text = "\n\n".join(conversation_text_lines).strip()
        if not conversation_text:
            st.error("No conversation content found to summarize.")
            return None

        if not json_template:
            st.error("No JSON template provided.")
            return None

        DynamicModel = create_dynamic_pydantic_model(json_template)
        if DynamicModel is None:
            st.error("Cannot create dynamic model from the provided JSON template. Please check the template format.")
            return None

        summary_prompt = f"""
Analyze the following conversation between a customer service agent and a customer.

Extract all relevant information mentioned in the conversation. For any information not mentioned or unclear, use null values.

Conversation:
{conversation_text}

Extract the information into the structured format based on the fields available in the schema.
"""

        with st.spinner("Generating conversation summary with dynamic structured outputs..."):
            completion = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": extraction_system_message},
                    {"role": "user", "content": summary_prompt},
                ],
                response_format=DynamicModel,
                temperature=0.1,
            )

        parsed_claim = completion.choices[0].message.parsed
        claim_dict = parsed_claim.model_dump()

        # Persist into conversation document
        conversation_doc["JSON_Summary"] = claim_dict
        conversation_doc["summary_generated_at"] = datetime.now(timezone.utc).isoformat()
        conversation_doc["extraction_method"] = "dynamic_structured_outputs"
        conversation_doc["template_used"] = json_template

        success = conversation_manager.save_conversation(conversation_doc)
        if success:
            st.success("✅ JSON summary generated and saved successfully using dynamic structured outputs!")
            with st.expander("📋 Generated JSON Summary", expanded=True):
                st.json(claim_dict)
            st.info("🎯 Used your custom JSON template for structured extraction!")
            st.session_state.conversation_doc = conversation_doc
        else:
            st.error("Failed to save the summary to the database.")
        return claim_dict
    except Exception as e:
        st.error(f"Error generating conversation summary: {e}")
        logger.error(f"generate_conversation_summary error: {e}")
        return None
