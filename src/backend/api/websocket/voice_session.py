"""
Voice Session Manager

Manages the lifecycle of voice sessions, integrating WebSocket connections
with customer context and conversation state.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket

from .connection_manager import connection_manager, VoiceSession
from .realtime_handler import realtime_handler

logger = logging.getLogger(__name__)


class VoiceSessionManager:
    """
    High-level manager for voice sessions
    
    Coordinates between connection management, realtime handling,
    and customer context.
    """
    
    def __init__(self):
        self.connection_manager = connection_manager
        self.realtime_handler = realtime_handler

    async def start_voice_session(
        self, 
        websocket: WebSocket, 
        customer_id: Optional[str] = None,
        session_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new voice session
        
        Args:
            websocket: Client WebSocket connection
            customer_id: Optional customer ID for context
            session_config: Optional session configuration overrides
            
        Returns:
            session_id: Unique session identifier
        """
        
        try:
            # Create WebSocket session
            session_id = await self.connection_manager.connect(websocket, customer_id)
            
            # Get session object
            session = self.connection_manager.get_session(session_id)
            if not session:
                raise Exception(f"Failed to create session {session_id}")
            
            logger.info(f"Starting voice session: {session}")
            
            # Send connection confirmation
            await websocket.send_text('{"type": "connection.established"}')
            
            # Handle the realtime session
            await self.realtime_handler.handle_session(websocket, session_id, customer_id)
            
            return session_id
            
        except Exception as e:
            logger.exception(f"Failed to start voice session: {e}")
            # Ensure cleanup
            await self.connection_manager.disconnect(websocket)
            raise
        finally:
            # Always cleanup on session end
            await self.connection_manager.disconnect(websocket)

    async def end_voice_session(self, websocket: WebSocket):
        """
        End a voice session
        """
        session = self.connection_manager.get_session_by_websocket(websocket)
        if session:
            logger.info(f"Ending voice session: {session}")
            
        await self.connection_manager.disconnect(websocket)

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        return self.connection_manager.get_connection_stats()

    async def send_to_customer_sessions(self, customer_id: str, message: Dict[str, Any]) -> int:
        """
        Send message to all sessions for a customer
        
        Returns:
            Number of sessions message was sent to
        """
        import json
        return await self.connection_manager.send_to_customer(
            customer_id, 
            json.dumps(message)
        )

    def get_customer_session_count(self, customer_id: str) -> int:
        """Get number of active sessions for a customer"""
        return len(self.connection_manager.get_customer_sessions(customer_id))


# Global session manager instance
voice_session_manager = VoiceSessionManager()