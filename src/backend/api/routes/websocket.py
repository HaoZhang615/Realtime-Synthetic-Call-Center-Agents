"""
WebSocket Routes for Realtime Voice Communication

Provides WebSocket endpoints for real-time voice chat functionality.
Based on patterns from openai-realtime-voice-template but adapted for
multi-agent voice bot architecture.
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse

# Import WebSocket infrastructure
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from websocket.voice_session import voice_session_manager

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

# Session configuration for frontend
REALTIME_SESSION_CONFIG = {
    "instructions": "You are a helpful voice assistant for a call center. Please respond with both text and audio. Always provide an audio response.",
    "voice": "shimmer",
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16", 
    "modalities": ["text", "audio"],
    "input_audio_transcription": {
        "model": "whisper-1"
    },
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 200
    },
    "temperature": 0.8,
    "max_response_output_tokens": 4096
}

# Transcription configuration for real-time transcription
TRANSCRIPTION_SESSION_CONFIG = {
    "model": "whisper-1", 
    "language": "en",
    "temperature": 0.0,
    "response_format": "verbose_json"
}


@websocket_router.get("/session/config")
async def get_session_config():
    """
    Get the session configuration for OpenAI Realtime API
    
    This endpoint provides session configuration that the frontend
    will use to configure the realtime connection.
    """
    return REALTIME_SESSION_CONFIG


@websocket_router.get("/transcription/config") 
async def get_transcription_config():
    """
    Get the transcription session configuration
    
    This provides configuration for real-time audio transcription.
    """
    return TRANSCRIPTION_SESSION_CONFIG


@websocket_router.websocket("/realtime")
async def realtime_websocket_endpoint(
    websocket: WebSocket,
    customer_id: Optional[str] = Query(None, description="Customer ID for context")
):
    """
    WebSocket endpoint for real-time voice communication
    
    This is the main endpoint that frontend connects to for voice chat.
    It bridges the browser WebSocket to Azure OpenAI Realtime API.
    
    Query Parameters:
        customer_id: Optional customer ID for customer context
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    logger.info(f"Realtime client connecting from {client_ip} for customer {customer_id}")
    
    try:
        # Start voice session - this handles the complete lifecycle
        await voice_session_manager.start_voice_session(
            websocket=websocket,
            customer_id=customer_id
        )
        
    except WebSocketDisconnect:
        logger.info(f"Realtime client {client_ip} disconnected normally")
    except Exception as e:
        logger.exception(f"Realtime WebSocket error for client {client_ip}: {e}")
        try:
            # Try to send error to client before closing
            await websocket.send_text(f'{{"type": "error", "error": "{str(e)}"}}')
        except:
            pass
    finally:
        # Ensure session cleanup
        try:
            await voice_session_manager.end_voice_session(websocket)
        except:
            pass
        logger.info(f"Realtime client {client_ip} session ended")


@websocket_router.websocket("/transcription")
async def transcription_websocket_endpoint(
    websocket: WebSocket,
    customer_id: Optional[str] = Query(None, description="Customer ID for context")
):
    """
    WebSocket endpoint for real-time transcription
    
    This endpoint provides real-time transcription services.
    It's separate from the main realtime endpoint to allow
    independent transcription functionality.
    
    Query Parameters:
        customer_id: Optional customer ID for context
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    logger.info(f"Transcription client connecting from {client_ip} for customer {customer_id}")
    
    try:
        await websocket.accept()
        
        # Send connection established
        await websocket.send_text('{"type": "connection.established"}')
        
        # For now, this is a placeholder - real transcription integration
        # would connect to Azure OpenAI transcription endpoint
        while True:
            message = await websocket.receive_text()
            # Echo back for now - implement actual transcription logic
            await websocket.send_text(f'{{"type": "transcription.echo", "message": "{message}"}}')
            
    except WebSocketDisconnect:
        logger.info(f"Transcription client {client_ip} disconnected")
    except Exception as e:
        logger.exception(f"Transcription WebSocket error for client {client_ip}: {e}")
    finally:
        logger.info(f"Transcription client {client_ip} session ended")


@websocket_router.get("/sessions/stats")
async def get_session_stats():
    """
    Get statistics about active voice sessions
    
    Returns information about active connections, customers, and agents.
    """
    try:
        stats = voice_session_manager.get_session_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        logger.exception(f"Failed to get session stats: {e}")
        return JSONResponse(
            status_code=500, 
            content={"error": "Failed to get session stats"}
        )


@websocket_router.post("/sessions/{customer_id}/broadcast")
async def broadcast_to_customer(customer_id: str, message: dict):
    """
    Broadcast a message to all sessions for a specific customer
    
    This allows other parts of the system to send messages to
    active voice sessions for a customer.
    """
    try:
        count = await voice_session_manager.send_to_customer_sessions(customer_id, message)
        return {"status": "sent", "session_count": count}
    except Exception as e:
        logger.exception(f"Failed to broadcast to customer {customer_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to broadcast message"}
        )