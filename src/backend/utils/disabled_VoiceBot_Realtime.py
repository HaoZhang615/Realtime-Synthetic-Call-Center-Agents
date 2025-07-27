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
    clear_audio_buffer,
    force_clear_audio_buffer,
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


# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = []

@st.fragment(run_every=1)
def conversation_display():
    
    # Get conversation items from the realtime client (structured approach like realtime2.py)
    conversation_items = getattr(st.session_state.realtime_client, 'conversation_items', [])
    
    # Check if conversation items have changed and force rerun if needed
    current_items_count = len(conversation_items)
    if current_items_count != st.session_state.get('last_items_count', 0):
        st.session_state.last_items_count = current_items_count
    
    # Build messages list from structured conversation items
    all_messages = []
    
    # Add conversation items (both text and voice)
    for item in conversation_items:
        if item.get("type") == "message" and item.get("content"):
            message = {
                "role": item["role"],
                "content": item["content"],
                "source": item.get("source", "unknown"),
                "timestamp": item.get("timestamp", "")
            }
            all_messages.append(message)
            
    # If no structured items available, fallback to transcript parsing for backward compatibility
    if not all_messages:
        # Fallback to old transcript parsing
        transcript = st.session_state.realtime_client.transcript
        
        if transcript.strip():
            message_blocks = transcript.split('\n\n')
            
            for block in message_blocks:
                block = block.strip()
                if not block:
                    continue
                
                # Parse user messages (voice input)
                if block.startswith("**You:**"):
                    user_text = block.replace("**You:**", "").strip()
                    if user_text:
                        all_messages.append({
                            "role": "user", 
                            "content": user_text,
                            "source": "voice"
                        })
                
                # Parse assistant messages (voice responses)
                elif block.startswith("**Assistant:**"):
                    assistant_text = block.replace("**Assistant:**", "").strip()
                    if assistant_text:
                        all_messages.append({
                            "role": "assistant", 
                            "content": assistant_text,
                            "source": "voice"
                        })
    
    # Update session state with all messages
    st.session_state.messages = all_messages
    
    # Display all messages using Streamlit's chat interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show source indicator
            source_indicator = "🎤" if message.get("source") == "voice" else "⌨️" if message.get("source") == "text" else ""
            if source_indicator:
                st.caption(f"{source_indicator} {message.get('source', 'unknown').title()}")
            
            # Show timestamp if available
            if message.get("timestamp"):
                try:
                    from datetime import datetime
                    ts = datetime.fromisoformat(message["timestamp"].replace('Z', '+00:00'))
                    st.caption(f"⏰ {ts.strftime('%H:%M:%S')}")
                except:
                    pass
            
            # Show audio indicator if this is an assistant message and audio is playing
            if message["role"] == "assistant" and len(audio_buffer) > 0:
                st.caption("🔊 *Playing audio response...*")
    
    # Show empty state if no messages
    if not st.session_state.messages:
        st.info("💬 Start a conversation by typing a message or recording audio below")


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
st.set_page_config(
    page_title="Realtime Voice Assistant",
    page_icon="🎤",
    layout="wide"
)

st.title("🎤 Azure OpenAI Realtime Voice Assistant")
st.markdown("Experience real-time voice and text conversations with Azure OpenAI GPT-4o")

# Load CSS styling if available
css_path = os.path.join(os.path.dirname(__file__), "common.css")
if os.path.exists(css_path):
    load_css(css_path)

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

# Track conversation items count for detecting changes
if "last_items_count" not in st.session_state:
    st.session_state.last_items_count = 0

# Track connection attempts to avoid infinite loops
if "connection_attempted" not in st.session_state:
    st.session_state.connection_attempted = False

# Automatic connection on page load
endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
if endpoint and not st.session_state.connection_attempted:
    st.session_state.connection_attempted = True
    
    try:
        # Initialize client if not already done
        if st.session_state.realtime_client is None:
            st.session_state.realtime_client = setup_realtime_client(
                st.session_state.event_loop
            )
        
        if st.session_state.realtime_client is not None:
            # Check if already connected, if not then connect
            if not st.session_state.realtime_client.is_connected():
                logger.info("🔗 Auto-connecting to Azure OpenAI Realtime API...")
                
                # Connect to Azure OpenAI
                run_async_in_loop(
                    st.session_state.realtime_client.connect(),
                    st.session_state.event_loop
                )
                
                if st.session_state.realtime_client.is_connected():
                    logger.info("✅ Successfully auto-connected to Azure OpenAI Realtime API")
                else:
                    logger.warning("❌ Auto-connection to Azure OpenAI Realtime API failed")
            else:
                logger.info("✅ Already connected to Azure OpenAI Realtime API")
        else:
            logger.error("❌ Failed to initialize Azure OpenAI client")
            
    except (ValueError, OSError, ConnectionError) as e:
        logger.error(f"❌ Auto-connection error: {str(e)}")
        if "authentication" in str(e).lower():
            logger.info("💡 Authentication error - may need to run `az login`")

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
        index=available_voices.index(st.session_state.selected_voice),
        help="Choose the voice for AI audio responses"
    )
    
    # Show current voice info
    st.caption(f"🔊 Current voice: **{st.session_state.selected_voice}**")
    
    st.markdown("---")
    
    # Voice Recording Section
    st.subheader("🎤 Voice Recording")
    
    # Check if we're connected before allowing interaction
    is_connected = (st.session_state.realtime_client and 
                    st.session_state.realtime_client.is_connected())
    
    # Recording button
    button_text = "🛑 Stop Recording" if st.session_state.recording else "🎤 Start Recording"
    button_type = "secondary" if st.session_state.recording else "primary"
    
    def voice_recording_callback():
        toggle_recording(
            st.session_state,
            st.session_state.realtime_client,
            st.session_state.recorder,
            st.session_state.selected_voice,
            send_on_stop=False  # Just drop the buffer without sending to AI
        )
    
    if st.button(
        button_text, 
        on_click=voice_recording_callback, 
        type=button_type, 
        key="audio_button",
        disabled=not is_connected,
        help="Start/Stop recording (stops without sending to AI)" if is_connected else "Connect to Azure OpenAI first",
        use_container_width=True
    ):
        pass  # Callback handles the logic
    
    # Recording status indicator
    if not is_connected:
        st.info("🔌 Connect to Azure OpenAI to enable voice recording")
    elif st.session_state.recording:
        st.success("🔴 **Recording in progress...**")
        st.caption("Click 'Stop Recording' to drop audio without sending")
    else:
        st.info("⚪ **Ready to record**")
        st.caption("Click 'Start Recording' to begin voice input")
    
    st.markdown("---")
    
    # Conversation Management Section
    st.subheader("💬 Conversation")
    if st.session_state.messages:
        st.write(f"**Messages:** {len(st.session_state.messages)}")
        
        # Count user vs assistant messages
        user_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
        assistant_msgs = len([m for m in st.session_state.messages if m["role"] == "assistant"])
        st.write(f"**You:** {user_msgs} | **Assistant:** {assistant_msgs}")
        
        # Button to clear conversation
        if st.button("🗑️ Clear Conversation"):
            st.session_state.messages = []
            # Also clear the realtime client transcript and conversation items
            if st.session_state.realtime_client:
                st.session_state.realtime_client.transcript = ""
                if hasattr(st.session_state.realtime_client, 'conversation_items'):
                    st.session_state.realtime_client.conversation_items = []
            st.rerun()
    else:
        st.write("No messages yet")
    
    st.markdown("---")
    

# Main content area
# Show connection status at the top
if st.session_state.realtime_client and st.session_state.realtime_client.is_connected():
    st.success("✅ **Connected to Azure OpenAI Realtime API** (Auto-connected)")
elif not endpoint:
    st.warning("⚠️ **Azure OpenAI not configured.** Please set the `AZURE_OPENAI_ENDPOINT` environment variable.")
elif st.session_state.connection_attempted:
    # Auto-connection was attempted but failed
    col1, col2 = st.columns([3, 1])
    with col1:
        st.error("❌ **Auto-connection failed.** Check your Azure credentials.")
    with col2:
        if st.button("🔄 Retry", key="retry_connection"):
            # Reset connection attempt flag and try again
            st.session_state.connection_attempted = False
            st.rerun()
else:
    st.info("� **Connecting automatically...**")

# Create a container with fixed height and scroll bar for conversation history
st.markdown("### 💬 Conversation")
conversation_container = st.container(height=600, border=True)

with conversation_container:
    conversation_display()

# Check if we're connected before allowing interaction (moved to sidebar)
# is_connected is now defined in the sidebar

# Debug: Show connection state for troubleshooting
if st.session_state.realtime_client:
    is_connected_main = st.session_state.realtime_client.is_connected()
    if not is_connected_main:
        st.info(f"🔍 **Debug:** realtime_client exists: {st.session_state.realtime_client is not None}, "
               f"is_connected: {is_connected_main}, "
               f"connection_attempted: {st.session_state.connection_attempted}")

# Handle new text message using chat_input  
if text_prompt := st.chat_input(
    "Type your message here..." if (st.session_state.realtime_client and st.session_state.realtime_client.is_connected()) else "Connect to Azure OpenAI first...",
    disabled=not (st.session_state.realtime_client and st.session_state.realtime_client.is_connected())
):
    if (st.session_state.realtime_client and 
        st.session_state.realtime_client.is_connected() and 
        text_prompt.strip()):
        # Send the message to the realtime API (this will add it to conversation_items)
        send_text_message(
            text_prompt.strip(),
            st.session_state.realtime_client,
            st.session_state.selected_voice
        )

# Start audio components
audio_player()
audio_recorder()
