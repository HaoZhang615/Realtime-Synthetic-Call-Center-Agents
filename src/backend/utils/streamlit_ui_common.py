"""
Common Streamlit UI utilities for VoiceBot applications.
This module contains shared UI components and layouts used across VoiceBot pages.
"""

import streamlit as st
from audio_recorder_streamlit import audio_recorder
from typing import Optional, Callable


def setup_page_header(title: str, subtitle: Optional[str] = None):
    """
    Set up consistent page header for VoiceBot applications.
    
    Args:
        title: Main page title
        subtitle: Optional subtitle or description
    """
    st.title(title)
    if subtitle:
        st.markdown(f"*{subtitle}*")


def setup_sidebar_header():
    """
    Set up consistent sidebar header.
    """
    with st.sidebar:
        st.header("🎛️ Configuration")


def setup_voice_input_recorder() -> Optional[bytes]:
    """
    Set up voice input recorder in sidebar.
    
    Returns:
        Optional[bytes]: Audio bytes if recorded, None otherwise
    """
    with st.sidebar:
        st.subheader("🎙️ Voice Input")
        custom_audio_bytes = audio_recorder(
            text="Click to record",
            recording_color="#e8b62c",
            neutral_color="#6aa36f",
            icon_size="2x",
            sample_rate=41_000,
            pause_threshold=3.0
            )
        return custom_audio_bytes


def setup_system_message_input(default_message: str) -> str:
    """
    Set up system message configuration in sidebar.
    
    Args:
        default_message: Default system message
        
    Returns:
        str: Configured system message
    """
    with st.sidebar:
        if "system_message" not in st.session_state:
            st.session_state.system_message = default_message
            
        st.session_state.system_message = st.text_area(
            "🧠 System Instructions:",
            value=st.session_state.system_message,
            height="content",
            help="Define the AI assistant's behavior and capabilities",

        )
        
        return st.session_state.system_message


def setup_voice_instruction_examples():
    """
    Set up expandable voice instruction examples in sidebar.
    """
    with st.sidebar:
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


def create_chat_container(height: int = 600):
    """
    Create a scrollable chat container.
    
    Args:
        height: Height of the container in pixels
        
    Returns:
        Chat container object
    """
    return st.container(height=height, border=False)


def process_user_input(speech_to_text_func: Optional[Callable] = None) -> Optional[str]:
    """
    Process user input from both text and voice sources.
    
    Args:
        speech_to_text_func: Function to convert speech to text
        
    Returns:
        Optional[str]: User input or None
    """
    # Handle text input
    text_prompt = st.chat_input("Ask me anything!")
    
    # Handle voice input
    voice_prompt = None
    if "voice_prompt" in st.session_state:
        voice_prompt = st.session_state.voice_prompt
        del st.session_state.voice_prompt
    
    return text_prompt or voice_prompt


def handle_audio_recording(audio_bytes: bytes, speech_to_text_func: Callable):
    """
    Handle audio recording and convert to text.
    
    Args:
        audio_bytes: Raw audio bytes
        speech_to_text_func: Function to convert speech to text
    """
    if audio_bytes:
        st.session_state.voice_prompt = speech_to_text_func(audio_bytes)


def display_chat_message(role: str, content: str, voice_enabled: bool = False, 
                        tts_func: Optional[Callable] = None):
    """
    Display a chat message with optional voice output.
    
    Args:
        role: Message role (user/assistant)
        content: Message content
        voice_enabled: Whether voice output is enabled
        tts_func: Text-to-speech function
    """
    with st.chat_message(role):
        st.markdown(content)
        
        if role == "assistant" and voice_enabled and tts_func:
            try:
                # Clean text for TTS
                from utils.voicebot_common import cleanup_response_for_tts
                audio_text = cleanup_response_for_tts(content)
                
                audio_content = tts_func(audio_text)
                if audio_content:
                    st.audio(audio_content, format="audio/wav", autoplay=True)
            except Exception as e:
                st.warning("Could not generate audio for this response")


def show_processing_spinner(message: str = "🤔 Processing your request..."):
    """
    Show a processing spinner with custom message.
    
    Args:
        message: Loading message to display
        
    Returns:
        Spinner context manager
    """
    return st.spinner(message)


def setup_sidebar_status_section(status_items: dict):
    """
    Set up a status section in the sidebar.
    
    Args:
        status_items: Dictionary of status items to display
    """
    with st.sidebar:
        st.subheader("🔧 System Status")
        for key, value in status_items.items():
            if isinstance(value, bool):
                status = "✅ Active" if value else "❌ Inactive"
                st.write(f"**{key}:** {status}")
            else:
                st.write(f"**{key}:** {value}")


def add_sidebar_separator():
    """Add a separator line in the sidebar."""
    with st.sidebar:
        st.markdown("---")


def setup_conversation_reset_button(reset_callback: Optional[Callable] = None):
    """
    Set up conversation reset button in sidebar.
    
    Args:
        reset_callback: Optional callback function when reset is clicked
    """
    with st.sidebar:
        if st.button("🔄 New Conversation"):
            # Default reset behavior
            keys_to_clear = ["conversation_doc", "messages", "connected_agents", 
                           "agent_thread"]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Call custom reset callback if provided
            if reset_callback:
                reset_callback()
            
            st.rerun()


def initialize_session_messages():
    """Initialize messages in session state if not present."""
    if "messages" not in st.session_state:
        st.session_state.messages = []


def add_message_to_session(role: str, content: str):
    """
    Add a message to the session state messages.
    
    Args:
        role: Message role (user/assistant/system)
        content: Message content
    """
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    st.session_state.messages.append({"role": role, "content": content})


def display_all_messages(exclude_system: bool = True):
    """
    Display all messages from session state.
    
    Args:
        exclude_system: Whether to exclude system messages from display
    """
    for message in st.session_state.messages:
        if exclude_system and message["role"] == "system":
            continue
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_chat_flow(user_input: str, chat_function: Callable, voice_enabled: bool = False,
                    tts_function: Optional[Callable] = None):
    """
    Handle the complete chat flow: add user message, get response, display both.
    
    Args:
        user_input: User's input message
        chat_function: Function to process the chat and get response
        voice_enabled: Whether voice output is enabled
        tts_function: Text-to-speech function
    """
    # Add user message
    add_message_to_session("user", user_input)
    
    # Display conversation history
    display_all_messages()
    
    # Get and display assistant response
    with st.chat_message("assistant"):
        with show_processing_spinner():
            # Pass previous conversation history excluding system messages
            conversation_history = [msg for msg in st.session_state.messages if msg["role"] != "system"]
            response = chat_function(user_input, conversation_history)
        
        # Display text response
        st.markdown(response)
        
        # Handle voice output
        if voice_enabled and tts_function:
            try:
                from utils.voicebot_common import cleanup_response_for_tts
                audio_text = cleanup_response_for_tts(response)
                audio_content = tts_function(audio_text)
                if audio_content:
                    st.audio(audio_content, format="audio/wav", autoplay=True)
            except Exception:
                st.warning("Could not generate audio for this response")
    
    # Add assistant response to session
    add_message_to_session("assistant", response)
