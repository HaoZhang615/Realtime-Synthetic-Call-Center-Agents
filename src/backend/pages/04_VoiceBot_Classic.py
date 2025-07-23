from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from audio_recorder_streamlit import audio_recorder
import streamlit as st
import io
import re
import os
import sys
import logging
import hashlib
from utils import load_dotenv_from_azd
from utils.conversation_manager import ConversationManager
from azure.monitor.opentelemetry import configure_azure_monitor

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

logging.captureWarnings(True)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO").upper())
# Raising the azure log level to WARN as it is too verbose
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())

if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

logger = logging.getLogger(__name__)
logger.debug("Starting VoiceBot Classic page")

# Load environment variables from azd
load_dotenv_from_azd()
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
# Azure Open AI Configuration
api_base = os.environ["AZURE_OPENAI_ENDPOINT"]
api_version = "2025-03-01-preview"  # Updated to match streaming sample
gpt4omini = os.environ["AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT"]

# Audio model configurations from environment
transcribe_model = os.environ.get("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "gpt-4o-mini-transcribe")
tts_model = os.environ.get("AZURE_OPENAI_TTS_DEPLOYMENT", "gpt-4o-mini-tts")

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
    logger.error(f"Failed to initialize conversation manager: {e}")
    conversation_manager = None

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def get_session_id():
    """Generate a unique session ID for the current Streamlit session."""
    if "session_id" not in st.session_state:
        # Use Streamlit's session state to create a consistent session ID
        session_data = str(st.session_state)
        st.session_state.session_id = hashlib.md5(session_data.encode()).hexdigest()[:16]
    return st.session_state.session_id

def get_customer_id():
    """Generate or get customer ID for conversation partitioning."""
    if "customer_id" not in st.session_state:
        # For demo purposes, use session ID as customer ID
        # In production, this would be the actual authenticated user ID
        st.session_state.customer_id = f"demo_user_{get_session_id()}"
    return st.session_state.customer_id

def initialize_conversation():
    """Initialize or load conversation from Cosmos DB."""
    if "conversation_doc" not in st.session_state and conversation_manager:
        customer_id = get_customer_id()
        session_id = get_session_id()
        
        # Create new conversation document
        st.session_state.conversation_doc = conversation_manager.create_conversation_document(
            customer_id=customer_id,
            session_id=session_id
        )
        
        logger.info(f"Initialized new conversation: {st.session_state.conversation_doc['id']}")

def save_conversation_to_cosmos():
    """Save current conversation to Cosmos DB."""
    if conversation_manager and "conversation_doc" in st.session_state:
        success = conversation_manager.save_conversation(st.session_state.conversation_doc)
        if success:
            logger.debug("Conversation saved to Cosmos DB")
        else:
            logger.error("Failed to save conversation to Cosmos DB")

# Function STT
def speech_to_text(audio: bytes) -> str:
    buffer = io.BytesIO(audio)
    buffer.name = "audio.wav"
    transcription_result = client.audio.transcriptions.create(
    file=buffer,
    model=transcribe_model,
    # language="en",  # Optional
    # prompt="Audio is a tech podcast, expect technical terms",  # Optional
    response_format="json"  # Optional
)
    buffer.close()
    return transcription_result.text


# Function TTS - Using raw response pattern
def text_to_speech(text_input: str):
    response = client.audio.speech.create(
        model=tts_model,
        voice=st.session_state.selected_voice,  # Use selected voice from sidebar
        input=text_input,
        response_format="wav",
        instructions=st.session_state.tts_instructions  # Use custom instructions from sidebar
    )
    return response.content

st.title("Azure OpenAI powered Self Service Chatbot")

# Initialize conversation on page load
initialize_conversation()


# Sidebar Configuration -- BEGIN
with st.sidebar:
    # add toggle to turn on and off the audio player
    if "voice_on" not in st.session_state:
        st.session_state.voice_on = False
    st.session_state.voice_on = st.toggle(label="Enable Voice Output", value=st.session_state.voice_on)
    
    # Voice selection dropdown
    available_voices = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
    if "selected_voice" not in st.session_state:
        st.session_state.selected_voice = "shimmer"  # Default voice
    st.session_state.selected_voice = st.selectbox(
        "Select Voice:",
        available_voices,
        index=available_voices.index(st.session_state.selected_voice)
    )
    
    # TTS Instructions input
    if "tts_instructions" not in st.session_state:
        st.session_state.tts_instructions = "Speak with a Swiss German accent."  # Default instruction
    st.session_state.tts_instructions = st.text_input(
        "Voice Instructions:",
        value=st.session_state.tts_instructions,
        placeholder="Enter custom instructions for the voice (e.g., accent, tone, style...)",
        help="Customize how the AI should speak (accent, emotion, pace, etc.)"
    )
    # Expandable section with examples
    with st.expander("💡 Voice Instruction Examples"):
        st.markdown("""
        **🎭 Accents & Languages:**
        - "Speak with a British accent"
        - "Use an American Southern drawl"
        - "Speak with a French accent"
        - "Use a New York accent"
        
        **😊 Emotions & Tone:**
        - "Speak cheerfully and enthusiastically"
        - "Use a calm, soothing tone"
        - "Sound excited and energetic"
        - "Speak in a professional, serious tone"
        
        **⚡ Style & Pace:**
        - "Speak slowly and clearly"
        - "Use a fast, energetic pace"
        - "Speak like a news anchor"
        - "Use a conversational, friendly tone"
        
        **🎯 Character & Role:**
        - "Speak like a wise teacher"
        - "Sound like a helpful customer service agent"
        - "Use the tone of a storyteller"
        - "Speak like a confident presenter"
        
        **✨ Creative Examples:**
        - "Whisper mysteriously"
        - "Speak dramatically like in a movie"
        - "Use an upbeat radio DJ voice"
        - "Sound like you're giving a motivational speech"
        """)
    
    # System Message Configuration
    if "system_message" not in st.session_state:
        st.session_state.system_message = """You are a helpful voice assistant chatbot. 
You can have conversations with users on various topics.
Be friendly, helpful, and concise in your responses."""
    st.session_state.system_message = st.text_area(
        "System Message:",
        value=st.session_state.system_message,
        height=100,
        placeholder="Enter the system message to define the assistant's behavior...",
        help="Define how the AI assistant should behave and respond to users"
    )
    
    
    st.markdown("---")  # Add a separator line
    
    # Conversation Management Section
    st.subheader("💬 Conversation Info")
    if "conversation_doc" in st.session_state and st.session_state.conversation_doc:
        conv_doc = st.session_state.conversation_doc
        st.write(f"**Session ID:** `{conv_doc['session_id'][:8]}...`")
        st.write(f"**Messages:** {len(conv_doc['messages'])}")
        st.write(f"**Created:** {conv_doc['created_at'][:19].replace('T', ' ')}")
        
        # Button to start new conversation
        if st.button("🔄 Start New Conversation"):
            # Clear current conversation from session state
            if "conversation_doc" in st.session_state:
                del st.session_state.conversation_doc
            if "messages" in st.session_state:
                st.session_state.messages = []
            # Re-initialize
            initialize_conversation()
            st.rerun()
            
        # Show recent conversations
        with st.expander("📚 Recent Conversations"):
            if conversation_manager:
                try:
                    customer_id = get_customer_id()
                    recent_convs = conversation_manager.get_recent_conversations(customer_id, limit=5)
                    
                    if recent_convs:
                        for conv in recent_convs:
                            with st.container():
                                st.write(f"**{conv['created_at'][:19].replace('T', ' ')}**")
                                st.write(f"Messages: {len(conv['messages'])}")
                                if st.button(f"Load", key=f"load_{conv['id'][:8]}"):
                                    # Load this conversation
                                    st.session_state.conversation_doc = conv
                                    st.session_state.messages = [
                                        {"role": msg["role"], "content": msg["content"]} 
                                        for msg in conv["messages"]
                                    ]
                                    st.rerun()
                                st.markdown("---")
                    else:
                        st.write("No recent conversations found")
                except Exception as e:
                    st.error(f"Error loading conversations: {e}")
            else:
                st.write("Conversation manager not available")
    else:
        st.write("No active conversation")

    st.markdown("---")  # Add a separator line

    custom_audio_bytes = audio_recorder(
        text="Click the microphone to start recording\n",
        recording_color="#e8b62c",
        neutral_color="#6aa36f",
        icon_size="3x",
        sample_rate=41_000,
        # auto_start=False,
    )
    
    if custom_audio_bytes:
        # st.audio(custom_audio_bytes, format="audio/wav")
        # call speech to text function and display the result
        st.session_state.voice_prompt = speech_to_text(custom_audio_bytes)
# Sidebar Configuration -- END

# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = []

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
    
    # Save to Cosmos DB if conversation manager is available
    if conversation_manager and "conversation_doc" in st.session_state:
        try:
            # Add user message to conversation document
            conversation_manager.add_message_to_conversation(
                st.session_state.conversation_doc,
                role="user",
                content=user_request
            )
            
            # Add assistant response to conversation document
            conversation_manager.add_message_to_conversation(
                st.session_state.conversation_doc,
                role="assistant", 
                content=assistant_response
            )
            
            # Save to Cosmos DB
            save_conversation_to_cosmos()
            
        except Exception as e:
            logger.error(f"Error saving conversation to Cosmos DB: {e}")
    
    return assistant_response
  
# create a container with fixed height and scroll bar for conversation history
conversation_container = st.container(height = 600, border=False)
# Handle new message  
if text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
elif custom_audio_bytes:
    prompt = st.session_state.voice_prompt
    # Clear voice prompt after processing
    if "voice_prompt" in st.session_state:
        del st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display the conversation history
        for message in st.session_state.messages:
            if message["role"] != "system":  
                with st.chat_message(message["role"]):  
                    st.markdown(message["content"]) 
        with st.chat_message("assistant"):  
            result = basic_chat(prompt, st.session_state.messages)
            audio_text = re.sub(r'\([^)]*\)', '', result)
            # trim the result to remove all occurances of text wrapped within brackets, e.g. (source_page: "Nestle") and (source_url: "https://www.nestle.com/")
            st.markdown(result)
            if st.session_state.voice_on:
                st.audio(text_to_speech(audio_text), format="audio/mp3", autoplay=True)
        st.session_state.messages.append({"role": "assistant", "content": result})