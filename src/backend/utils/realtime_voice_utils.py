"""
Realtime Voice Bot Utilities

This module contains utility classes and functions for the Azure OpenAI 
Realtime Voice Assistant, including WebSocket client, audio recording, 
and audio playback functionality.
"""

import asyncio
import base64
import json
import threading
import numpy as np
import sounddevice as sd
import websockets
import logging
import os
import queue
from datetime import datetime
import tzlocal
from azure.identity import DefaultAzureCredential
from asyncio import run_coroutine_threadsafe

logger = logging.getLogger(__name__)

# Global audio buffer for real-time playback
audio_buffer = np.array([], dtype=np.int16)
buffer_lock = threading.Lock()


class SimpleRealtimeClient:
    """Simplified realtime client for Azure OpenAI GPT-4o Realtime Preview"""
    
    def __init__(self, event_loop=None, audio_buffer_cb=None, debug=False):
        # Azure OpenAI configuration
        self.azure_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
        self.azure_deployment = os.environ.get('AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT', 'gpt-4o-realtime-preview')
        self.api_version = "2024-10-01-preview"
        
        if not self.azure_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        
        # Construct Azure OpenAI WebSocket URL
        endpoint_base = self.azure_endpoint.replace('https://', '').rstrip('/')
        self.url = f'wss://{endpoint_base}/openai/realtime?api-version={self.api_version}&deployment={self.azure_deployment}'
        
        self.debug = debug
        self.event_loop = event_loop
        self.logs = []
        
        # Change: Use structured conversation items instead of single transcript string
        self.conversation_items = []  # List of conversation items
        self.transcript = ""  # Keep for backward compatibility
        
        self.current_text_response = ""
        self.current_audio_transcript = ""
        self.response_cancelled = False  # Track if current response was cancelled
        self.ws = None
        self._message_handler_task = None
        self.audio_buffer_cb = audio_buffer_cb
        self._credential = DefaultAzureCredential()

    def is_connected(self):
        """Check if websocket connection is active"""
        if self.ws is None:
            return False
        
        try:
            from websockets import State
            return self.ws.state == State.OPEN
        except (ImportError, AttributeError):
            try:
                if hasattr(self.ws, 'state') and hasattr(self.ws.state, 'name'):
                    return self.ws.state.name == 'OPEN'
                elif hasattr(self.ws, 'closed'):
                    return not self.ws.closed
                else:
                    return True
            except Exception:
                return False

    def log_event(self, event_type, event):
        if self.debug:
            local_timezone = tzlocal.get_localzone() 
            now = datetime.now(local_timezone).strftime("%H:%M:%S")
            msg = json.dumps(event)
            self.logs.append((now, event_type, msg))
        return True

    async def connect(self):
        if self.is_connected():
            raise Exception("Already connected")

        try:
            # Get Azure AD token for Azure OpenAI using Entra ID
            logger.info("🔑 Authenticating with Azure Entra ID...")
            token = self._credential.get_token("https://cognitiveservices.azure.com/.default")
            
            logger.info(f"🔗 Connecting to: {self.url}")
            
            # Connect with authentication headers
            try:
                headers_dict = {
                    "Authorization": f"Bearer {token.token}",
                }
                self.ws = await websockets.connect(self.url, extra_headers=headers_dict)
                logger.info("✅ Connected using extra_headers")
            except TypeError:
                headers_list = [
                    ("Authorization", f"Bearer {token.token}"),
                ]
                self.ws = await websockets.connect(self.url, additional_headers=headers_list)
                logger.info("✅ Connected using additional_headers")
            
            # Start the message handler
            self._message_handler_task = self.event_loop.create_task(self._message_handler())
            
            # Configure the session for audio output with server VAD for interruption
            session_config = {
                "modalities": ["text", "audio"],
                "instructions": "You are a helpful AI assistant for a call center. Be friendly, concise, and professional.",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 200
                }
            }
            
            logger.info("🎛️ Configuring session for audio output...")
            config_event = {
                "type": "session.update",
                **session_config
            }
            await self.ws.send(json.dumps(config_event))
            
            logger.info("✅ Connected successfully with Entra ID authentication!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            raise Exception(f"Azure Entra ID authentication failed: {str(e)}") from e

    async def _message_handler(self):
        try:
            while True:
                if not self.ws:
                    await asyncio.sleep(0.05)
                    continue
                    
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=0.05)
                    data = json.loads(message)
                    self.receive(data)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info("WebSocket connection closed")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error in message handler: {e}")
                    continue
        except Exception as e:
            logger.error(f"Message handler error: {e}")
        finally:
            # Ensure cleanup
            try:
                await self.disconnect()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self._message_handler_task:
            self._message_handler_task.cancel()
            try:
                await self._message_handler_task
            except asyncio.CancelledError:
                pass
        self._message_handler_task = None
        return True

    def handle_audio(self, event):
        # Check if we should ignore audio events (e.g., after cancellation)
        event_type = event.get("type", "")
        
        if event_type == "response.audio_transcript.delta":
            if not self.response_cancelled:
                self.current_audio_transcript += event.get("delta", "")

        elif event_type == "response.text.delta":
            if not self.response_cancelled:
                self.current_text_response += event.get("delta", "")

        elif event_type == "response.audio.delta" and self.audio_buffer_cb:
            # Only process audio if we haven't been interrupted
            if not self.response_cancelled:
                b64_audio_chunk = event.get("delta")
                if b64_audio_chunk:
                    try:
                        decoded_audio_chunk = base64.b64decode(b64_audio_chunk)
                        pcm_audio_chunk = np.frombuffer(decoded_audio_chunk, dtype=np.int16)
                        self.audio_buffer_cb(pcm_audio_chunk)
                    except Exception as e:
                        logger.error(f"❌ Error processing audio chunk: {e}")

        # Handle response completion
        elif event_type == "response.done":
            # Only process completion if not cancelled
            if not self.response_cancelled:
                final_response = self.current_text_response or self.current_audio_transcript
                if final_response.strip():
                    # Add to conversation items
                    conversation_item = {
                        "id": f"assistant_{int(datetime.now().timestamp() * 1000)}",
                        "type": "message",
                        "role": "assistant",
                        "content": final_response.strip(),
                        "source": "voice",
                        "timestamp": datetime.now().isoformat()
                    }
                    self.conversation_items.append(conversation_item)
                    
                    # Also update transcript for backward compatibility
                    self.transcript += f"\n\n**Assistant:** {final_response.strip()}"
            
            # Always reset response state
            self.current_text_response = ""
            self.current_audio_transcript = ""
            self.response_cancelled = False

    def receive(self, event):
        self.log_event("server", event)
        
        # Handle speech started - immediate interruption like realtime2.py
        if event.get("type") == "input_audio_buffer.speech_started":
            logger.info("🎤 Speech detected - interrupting current response")
            # Mark response as cancelled
            self.response_cancelled = True
            # Immediately clear audio buffer to stop current playback
            force_clear_audio_buffer()
            # Cancel any ongoing response
            try:
                self.send("response.cancel")
            except Exception as e:
                logger.error(f"Error cancelling response: {e}")
        
        # Handle response start - reset cancellation flag
        elif event.get("type") == "response.created":
            self.response_cancelled = False
            logger.info("🤖 New response started")
        
        # Handle all response-related events
        if any(keyword in event.get("type", "") for keyword in ["response.audio", "response.text", "response.done"]):
            self.handle_audio(event)
        
        # Handle input audio transcription - improved handling
        if event.get("type") == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            item_id = event.get("item_id", "")
            
            if transcript.strip():
                # Add to conversation items
                conversation_item = {
                    "id": item_id,
                    "type": "message",
                    "role": "user",
                    "content": transcript.strip(),
                    "source": "voice",
                    "timestamp": datetime.now().isoformat()
                }
                self.conversation_items.append(conversation_item)
                
                # Also update transcript for backward compatibility
                self.transcript += f"\n\n**You:** {transcript.strip()}"
                
                logger.info(f"🎤 Voice input transcribed: {transcript.strip()[:50]}...")
        
        # Handle conversation item creation
        if event.get("type") == "conversation.item.created":
            item = event.get("item", {})
            if item.get("role") == "assistant":
                # This is an assistant response
                content = ""
                if "content" in item:
                    for content_part in item["content"]:
                        if content_part.get("type") == "text":
                            content += content_part.get("text", "")
                
                if content.strip():
                    conversation_item = {
                        "id": item.get("id", ""),
                        "type": "message", 
                        "role": "assistant",
                        "content": content.strip(),
                        "source": "voice",
                        "timestamp": datetime.now().isoformat()
                    }
                    self.conversation_items.append(conversation_item)
        
        return True

    def send(self, event_name, data=None):
        if not self.is_connected():
            raise Exception("RealtimeAPI is not connected")
        
        data = data or {}
        if not isinstance(data, dict):
            raise ValueError("data must be a dictionary")
        
        event = {
            "type": event_name,
            **data
        }
        
        self.log_event("client", event)
        
        # Send the message asynchronously
        if self.event_loop and self.ws:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(event)), 
                self.event_loop
            )

        return True


class StreamingAudioRecorder:
    """Real-time audio recorder for voice input"""
    
    def __init__(self, sample_rate=24_000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.audio_thread = None

    def callback(self, indata, frames, time, status):
        """Called for each audio block that gets recorded"""
        if status:
            logger.warning(f"Audio recording status: {status}")
        
        if self.is_recording:
            try:
                self.audio_queue.put(indata.copy(), block=False)
            except queue.Full:
                logger.warning("Audio queue is full, dropping frame")
                # Remove oldest item and add new one
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put(indata.copy(), block=False)
                except queue.Empty:
                    pass

    def start_recording(self):
        if not self.is_recording:
            try:
                self.is_recording = True
                self.audio_thread = sd.InputStream(
                    dtype="int16",
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=self.callback,
                    blocksize=2_000
                )
                self.audio_thread.start()
                logger.info("🎤 Audio recording started successfully")
            except Exception as e:
                logger.error(f"❌ Failed to start audio recording: {e}")
                self.is_recording = False
                self.audio_thread = None
                raise

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            if self.audio_thread:
                try:
                    self.audio_thread.stop()
                    self.audio_thread.close()
                    logger.info("🛑 Audio recording stopped successfully")
                except Exception as e:
                    logger.error(f"❌ Error stopping audio recording: {e}")
                finally:
                    self.audio_thread = None
            
            # Clear the audio queue to prevent issues
            cleared_count = 0
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    cleared_count += 1
                except queue.Empty:
                    break
            
            if cleared_count > 0:
                logger.info(f"🧹 Cleared {cleared_count} audio chunks from queue")

    def get_audio_chunk(self):
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None


# Audio callback function for real-time playback
def audio_buffer_cb(pcm_audio_chunk):
    """Callback function so that our realtime client can fill the audio buffer"""
    global audio_buffer

    with buffer_lock:
        audio_buffer = np.concatenate([audio_buffer, pcm_audio_chunk])


def clear_audio_buffer():
    """Clear the audio buffer to stop current playback"""
    global audio_buffer
    
    with buffer_lock:
        audio_buffer = np.array([], dtype=np.int16)
        logger.info("🔇 Audio buffer cleared")


def force_clear_audio_buffer():
    """Aggressively clear audio buffer and force stop playback immediately"""
    global audio_buffer
    
    # Clear the buffer multiple times to ensure it's empty
    with buffer_lock:
        audio_buffer = np.array([], dtype=np.int16)
    
    # Force another clear after a tiny delay to catch any race conditions
    import time
    time.sleep(0.001)
    
    with buffer_lock:
        audio_buffer = np.array([], dtype=np.int16)
        
    logger.info("🔇 Audio buffer force-cleared for interruption")


# Callback function for real-time playback using sounddevice
def sd_audio_cb(outdata, frames, time, status):
    """Callback for sounddevice audio output stream"""
    global audio_buffer

    channels = 1

    with buffer_lock:
        if len(audio_buffer) >= frames:
            outdata[:] = audio_buffer[:frames].reshape(-1, channels)
            audio_buffer = audio_buffer[frames:]
        else:
            outdata.fill(0)


def start_audio_stream(session_state):
    """Start audio output stream for playing AI responses"""
    try:
        if not hasattr(session_state, 'audio_output_stream') or session_state.audio_output_stream is None:
            session_state.audio_output_stream = sd.OutputStream(
                callback=sd_audio_cb, 
                dtype="int16", 
                samplerate=24_000, 
                channels=1, 
                blocksize=2_000
            )
            session_state.audio_output_stream.start()
            logger.info("🔊 Audio output stream started")
    except Exception as e:
        logger.error(f"❌ Failed to start audio stream: {e}")
        session_state.audio_output_stream = None


def stop_audio_stream(session_state):
    """Stop audio output stream"""
    try:
        if hasattr(session_state, 'audio_output_stream') and session_state.audio_output_stream is not None:
            session_state.audio_output_stream.stop()
            session_state.audio_output_stream.close()
            session_state.audio_output_stream = None
            logger.info("🔇 Audio output stream stopped")
    except Exception as e:
        logger.error(f"❌ Failed to stop audio stream: {e}")


def create_event_loop():
    """Creates an event loop for async operations"""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    return loop, thread


def run_async_in_loop(coroutine, event_loop):
    """Helper for running an async function in the cached event loop"""
    return run_coroutine_threadsafe(coroutine, event_loop).result()


def setup_realtime_client(event_loop):
    """Setup the realtime client"""
    if not os.environ.get('AZURE_OPENAI_ENDPOINT'):
        return None
    
    return SimpleRealtimeClient(
        event_loop=event_loop, 
        audio_buffer_cb=audio_buffer_cb, 
        debug=True
    )


def get_audio_status(session_state):
    """Get audio playback status for display"""
    global audio_buffer
    
    if len(audio_buffer) > 0:
        return "playing", f"🔊 Playing audio ({len(audio_buffer)} samples remaining)"
    elif session_state.get("recording", False):
        return "recording", "🎤 Recording audio..."
    else:
        return "idle", "🔇 Audio idle"


def send_text_message(message, realtime_client, selected_voice):
    """Send a text message to the AI"""
    if realtime_client is None or not realtime_client.is_connected():
        return False, "Client not connected. Please connect to Azure OpenAI first."
    
    try:
        # Force clear audio buffer to stop any current playback when sending new message
        force_clear_audio_buffer()
        
        # Cancel any pending response to interrupt current AI response  
        realtime_client.send("response.cancel")
        
        # Add user message to conversation items
        conversation_item = {
            "id": f"msg_{int(datetime.now().timestamp() * 1000)}",
            "type": "message",
            "role": "user", 
            "content": message.strip(),
            "source": "text",
            "timestamp": datetime.now().isoformat()
        }
        realtime_client.conversation_items.append(conversation_item)
        
        # Add user message to transcript for backward compatibility
        realtime_client.transcript += f"\n\n**You:** {message.strip()}"
        
        # Send the message as a conversation item
        realtime_client.send("conversation.item.create", {
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": message
                    }
                ]
            }
        })
        
        # Request response with both text and audio
        realtime_client.send("response.create", {
            "response": {
                "modalities": ["text", "audio"],
                "voice": selected_voice
            }
        })
        logger.info(f"📤 Sent text message: {message[:50]}...")
        return True, "Message sent successfully"
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}")
        return False, f"Error sending message: {str(e)}"


def toggle_recording(session_state, realtime_client, recorder, selected_voice, send_on_stop=False):
    """Toggle audio recording state
    
    Args:
        session_state: Streamlit session state
        realtime_client: WebSocket client
        recorder: Audio recorder instance
        selected_voice: Voice for AI response
        send_on_stop: If True, sends audio buffer to AI when stopping. If False, just drops the buffer.
    """
    if realtime_client is None or not realtime_client.is_connected():
        return False, "Client not connected. Please connect to Azure OpenAI first."
        
    try:
        session_state.recording = not session_state.recording

        if session_state.recording:
            # Force clear audio buffer to stop any current playback when starting new recording
            force_clear_audio_buffer()
            
            # Cancel any pending response to interrupt current AI response
            realtime_client.send("response.cancel")
            
            # Clear any existing audio queue before starting
            while not recorder.audio_queue.empty():
                try:
                    recorder.audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            recorder.start_recording()
            logger.info("🎤 Started recording")
            return True, "Recording started"
        else:
            recorder.stop_recording()
            logger.info("🛑 Stopped recording")
            
            if send_on_stop:
                # Send the committed audio and request response
                try:
                    realtime_client.send("input_audio_buffer.commit")
                    # Request response with audio
                    realtime_client.send("response.create", {
                        "response": {
                            "modalities": ["text", "audio"],
                            "voice": selected_voice
                        }
                    })
                    logger.info("📤 Sent audio buffer and requested response")
                    return True, "Recording stopped and sent"
                except Exception as e:
                    logger.error(f"❌ Error sending audio: {e}")
                    return False, f"Error processing audio: {str(e)}"
            else:
                # Just drop the audio buffer without sending anything to AI
                try:
                    # Clear the input audio buffer on the server side to drop recorded audio
                    realtime_client.send("input_audio_buffer.clear")
                    logger.info("🗑️ Dropped audio buffer without sending to AI")
                    return True, "Recording stopped and dropped"
                except Exception as e:
                    logger.error(f"❌ Error clearing audio buffer: {e}")
                    return False, f"Error clearing buffer: {str(e)}"
                
    except Exception as e:
        logger.error(f"❌ Error in toggle_recording: {e}")
        # Reset recording state on error
        session_state.recording = False
        try:
            recorder.stop_recording()
        except:
            pass
        return False, f"Error with recording: {str(e)}"


def process_audio_chunks(session_state, realtime_client, recorder, max_chunks_per_cycle=10):
    """Process audio chunks from the recording queue"""
    if (session_state.recording and 
        realtime_client is not None and 
        realtime_client.is_connected()):
        # Drain what's in the queue and send it to Azure OpenAI
        try:
            chunks_processed = 0
            
            while (not recorder.audio_queue.empty() and 
                   chunks_processed < max_chunks_per_cycle):
                try:
                    chunk = recorder.audio_queue.get_nowait()
                    if chunk is not None and len(chunk) > 0:
                        encoded_chunk = base64.b64encode(chunk).decode()
                        realtime_client.send("input_audio_buffer.append", {"audio": encoded_chunk})
                        chunks_processed += 1
                except queue.Empty:
                    break
                except Exception as chunk_error:
                    logger.error(f"❌ Error processing individual audio chunk: {chunk_error}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Error in audio recorder: {e}")
            # Stop recording if there's a critical error
            session_state.recording = False
            try:
                recorder.stop_recording()
            except Exception as stop_error:
                logger.error(f"❌ Error stopping recorder: {stop_error}")


def cleanup_resources(session_state, realtime_client, recorder, event_loop):
    """Clean up audio resources and connections"""
    try:
        # Stop recording if active
        if session_state.get("recording", False):
            session_state.recording = False
            if recorder:
                recorder.stop_recording()
        
        # Stop audio stream if active
        stop_audio_stream(session_state)
        
        # Disconnect client if connected
        if realtime_client and realtime_client.is_connected():
            try:
                run_async_in_loop(realtime_client.disconnect(), event_loop)
            except Exception as e:
                logger.error(f"Error disconnecting client during cleanup: {e}")
                
        logger.info("🧹 Resources cleaned up successfully")
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
