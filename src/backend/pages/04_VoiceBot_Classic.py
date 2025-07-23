from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from audio_recorder_streamlit import audio_recorder
import streamlit as st
import io
import re
import os
import sys
import logging
from utils import load_dotenv_from_azd
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

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

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
    
    return response.choices[0].message.content
  
# create a container with fixed height and scroll bar for conversation history
conversation_container = st.container(height = 600, border=False)
# Handle new message  
if text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
elif custom_audio_bytes:
    prompt = st.session_state.voice_prompt
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