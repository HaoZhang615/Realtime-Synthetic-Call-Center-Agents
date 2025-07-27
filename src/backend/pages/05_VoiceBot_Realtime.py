import streamlit as st
import logging
import os
import sys
import atexit

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from utils import load_dotenv_from_azd
from utils.realtime_voice_utils import (
    StreamingAudioRecorder,
    start_audio_stream,
    create_event_loop,
    run_async_in_loop,
    setup_realtime_client,
    get_audio_status,
    send_text_message,
    toggle_recording,
    process_audio_chunks,
    cleanup_resources,
    audio_buffer
)

# Configure logging
logging.captureWarnings(True)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO").upper())
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())

try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
        configure_azure_monitor()
except ImportError:
    # Azure Monitor OpenTelemetry package not available
    pass

logger = logging.getLogger(__name__)

# Load environment variables from azd
load_dotenv_from_azd()


def load_css(file_path):
    """Load CSS styling"""
    with open(file_path, encoding='utf-8') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def get_session_id():
    """Generate a unique session ID for the current Streamlit session"""
    import hashlib
    if "session_id" not in st.session_state:
        session_data = str(st.session_state)
        st.session_state.session_id = hashlib.md5(session_data.encode()).hexdigest()[:16]
    return st.session_state.session_id


@st.fragment(run_every=1)
def conversation_display():
    """Display the conversation transcript with real-time updates"""
    if st.session_state.realtime_client is None:
        st.info("🔗 Connect to Azure OpenAI to start chatting")
        return
    
    if not st.session_state.realtime_client.is_connected():
        st.warning("⚠️ Not connected to Azure OpenAI. Please connect first.")
        return
    
    # Display conversation transcript
    transcript = st.session_state.realtime_client.transcript
    
    if transcript.strip():
        # Split transcript into messages and format them
        messages = transcript.split('\n\n')
        
        for message in messages:
            if message.strip():
                if message.startswith("**You:**"):
                    # User message
                    user_text = message.replace("**You:**", "").strip()
                    if user_text:
                        with st.chat_message("user"):
                            st.markdown(user_text)
                elif message.startswith("**Assistant:**"):
                    # Assistant message
                    assistant_text = message.replace("**Assistant:**", "").strip()
                    if assistant_text:
                        with st.chat_message("assistant"):
                            st.markdown(assistant_text)
                            
                            # Show audio indicator if audio is playing
                            if len(audio_buffer) > 0:
                                st.caption("🔊 *Playing audio response...*")
    else:
        st.caption("*Start a conversation by typing a message or recording audio*")


@st.fragment(run_every=1)
def audio_player():
    """Handle audio playback"""
    if not st.session_state.audio_stream_started:
        st.session_state.audio_stream_started = True
        start_audio_stream(st.session_state)


@st.fragment(run_every=1)
def audio_recorder():
    """Handle audio recording"""
    process_audio_chunks(
        st.session_state,
        st.session_state.realtime_client,
        st.session_state.recorder,
        max_chunks_per_cycle=10
    )


# Initialize Streamlit page
st.title("Azure OpenAI Realtime Voice Assistant")

# Register cleanup function to run on app shutdown
if "cleanup_registered" not in st.session_state:
    # Register cleanup function
    # Register cleanup function that will be called with current session state
    def cleanup_on_exit():
        try:
            if hasattr(st.session_state, 'realtime_client'):
                cleanup_resources(
                    st.session_state,
                    st.session_state.get('realtime_client'),
                    st.session_state.get('recorder'),
                    st.session_state.get('event_loop')
                )
        except (RuntimeError, ValueError) as e:
            logger.error("Error during cleanup: %s", e)
    
    atexit.register(cleanup_on_exit)
    st.session_state.cleanup_registered = True

# Initialize session state
if "event_loop" not in st.session_state:
    st.session_state.event_loop, worker_thread = create_event_loop()

if "realtime_client" not in st.session_state:
    st.session_state.realtime_client = None

if "recorder" not in st.session_state:
    st.session_state.recorder = StreamingAudioRecorder()

if "recording" not in st.session_state:
    st.session_state.recording = False

if "audio_stream_started" not in st.session_state:
    st.session_state.audio_stream_started = False

if "audio_output_stream" not in st.session_state:
    st.session_state.audio_output_stream = None

# Voice selection in sidebar
with st.sidebar:
    st.subheader("🎤 Voice Settings")
    
    # Voice selection dropdown
    available_voices = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
    if "selected_voice" not in st.session_state:
        st.session_state.selected_voice = "alloy"
    st.session_state.selected_voice = st.selectbox(
        "Select Voice:",
        available_voices,
        index=available_voices.index(st.session_state.selected_voice)
    )
    
    st.markdown("---")
    
    # Connection status
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
    if not endpoint:
        st.error("⚠️ Azure OpenAI not configured")
        st.write("Required: `AZURE_OPENAI_ENDPOINT`")
    else:
        st.success("✅ Azure OpenAI configured")
        deployment = os.environ.get('AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT', 'gpt-4o-realtime-preview')
        st.write(f"Endpoint: {endpoint.split('//')[1] if '//' in endpoint else endpoint}")
        st.write(f"Deployment: {deployment}")
    
    # Audio status indicator
    status_type, status_message = get_audio_status(st.session_state)
    if status_type == "playing":
        st.success(status_message)
    elif status_type == "recording":
        st.info(status_message)
    else:
        st.caption(status_message)
    
    # Connection debug info
    if st.session_state.realtime_client:
        connection_status = "Connected" if st.session_state.realtime_client.is_connected() else "Disconnected"
        st.caption(f"**Status:** {connection_status}")
        if hasattr(st.session_state.realtime_client, 'ws') and st.session_state.realtime_client.ws:
            try:
                ws_state = st.session_state.realtime_client.ws.state.name
                st.caption(f"**WebSocket:** {ws_state}")
            except (AttributeError, ImportError):
                st.caption("**WebSocket:** Unknown state")
    else:
        st.caption("**Status:** Not initialized")
    
    # Connect button
    if st.button("🔗 Connect", type="primary", disabled=not endpoint):
        if not endpoint:
            st.error("Please configure AZURE_OPENAI_ENDPOINT first")
        else:
            with st.spinner("Connecting with Entra ID..."):
                try:
                    # Initialize client if not already done
                    if st.session_state.realtime_client is None:
                        st.session_state.realtime_client = setup_realtime_client(
                            st.session_state.event_loop
                        )
                    
                    if st.session_state.realtime_client is None:
                        st.error("Failed to initialize Azure OpenAI client")
                    else:
                        # Disconnect first if already connected
                        if st.session_state.realtime_client.is_connected():
                            run_async_in_loop(
                                st.session_state.realtime_client.disconnect(),
                                st.session_state.event_loop
                            )
                        
                        # Connect to Azure OpenAI
                        run_async_in_loop(
                            st.session_state.realtime_client.connect(),
                            st.session_state.event_loop
                        )
                        
                        if st.session_state.realtime_client.is_connected():
                            st.success("Connected to Azure OpenAI Realtime API")
                            # Don't call st.rerun() to avoid losing connection state
                        else:
                            st.error("Failed to connect to Azure OpenAI Realtime API")
                except (ValueError, OSError, ConnectionError) as e:
                    st.error(f"Error connecting: {str(e)}")
                    if "authentication" in str(e).lower():
                        st.info("💡 Try running `az login` in your terminal first")
    
    # Show disconnect button if connected
    if (st.session_state.realtime_client and 
        st.session_state.realtime_client.is_connected() and 
        st.button("🔌 Disconnect", type="secondary")):
        try:
            run_async_in_loop(
                st.session_state.realtime_client.disconnect(),
                st.session_state.event_loop
            )
            st.success("Disconnected from Azure OpenAI Realtime API")
        except (OSError, RuntimeError) as e:
            st.error(f"Error disconnecting: {str(e)}")

# Main content area
# Show connection status at the top
if st.session_state.realtime_client and st.session_state.realtime_client.is_connected():
    st.success("✅ **Connected to Azure OpenAI Realtime API**")
elif not endpoint:
    st.warning("⚠️ **Azure OpenAI not configured.** Please set the `AZURE_OPENAI_ENDPOINT` environment variable.")
elif st.session_state.realtime_client and not st.session_state.realtime_client.is_connected():
    st.warning("⚠️ **Disconnected from Azure OpenAI.** Please reconnect using the sidebar.")
else:
    st.info("🔗 **Ready to connect.** Click the Connect button in the sidebar.")

# Conversation container
with st.container(height=400, border=True):
    conversation_display()

# Input section
st.markdown("### 💬 Chat with the Assistant")

# Check if we're connected before allowing text interaction
is_connected = (st.session_state.realtime_client and 
                st.session_state.realtime_client.is_connected())

# Text input
with st.form(key="text_message_form", clear_on_submit=True):
    text_input = st.text_area(
        "Type your message:", 
        height=100,
        placeholder="Ask me anything..." if is_connected else "Connect to Azure OpenAI first...",
        key="form_text_input",
        disabled=not is_connected
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        submitted = st.form_submit_button(
            "💬 Send", 
            type="primary",
            disabled=not is_connected
        )
    
    with col2:
        if not is_connected:
            st.caption("🔌 Connect to Azure OpenAI to enable chat")
        elif text_input.strip():
            st.caption(f"Message length: {len(text_input)} characters")
    
    if submitted and is_connected:
        if text_input.strip():
            if send_text_message(
                text_input.strip(),
                st.session_state.realtime_client,
                st.session_state.selected_voice
            ):
                st.success("Message sent!")
                # Don't call st.rerun() to avoid connection issues
        else:
            st.warning("Please enter a message")

# Voice input
st.markdown("### 🎤 Voice Chat")
col1, col2 = st.columns([1, 1])

# Check if we're connected before allowing voice interaction
is_connected = (st.session_state.realtime_client and 
                st.session_state.realtime_client.is_connected())

with col1:
    button_text = "🛑 Stop Recording" if st.session_state.recording else "🎤 Start Recording"
    button_type = "secondary" if st.session_state.recording else "primary"
    def voice_recording_callback():
        toggle_recording(
            st.session_state,
            st.session_state.realtime_client,
            st.session_state.recorder,
            st.session_state.selected_voice
        )
    
    st.button(
        button_text, 
        on_click=voice_recording_callback, 
        type=button_type, 
        key="audio_button",
        disabled=not is_connected,
        help="Connect to Azure OpenAI first" if not is_connected else None
    )

with col2:
    if not is_connected:
        st.warning("🔌 Not connected - Connect first")
    elif st.session_state.recording:
        st.success("🔴 Recording in progress...")
    else:
        st.info("⚪ Ready to record")

# Start audio components
audio_player()
audio_recorder()
