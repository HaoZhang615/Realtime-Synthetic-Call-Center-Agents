"""
Voice Session Manager

Manages the lifecycle of voice sessions, integrating WebSocket connections
with customer context and conversation state.
"""

import logging
from datetime import datetime, timezone
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
            # Only cleanup on error - normal cleanup happens in end_voice_session
            await self.connection_manager.disconnect(websocket)
            raise

    async def end_voice_session(self, websocket: WebSocket):
        """
        End a voice session and log conversation to Cosmos DB
        """
        session = self.connection_manager.get_session_by_websocket(websocket)
        
        if session:
            logger.info(f"Ending voice session: {session}")
            
            # Mark session end time
            session.session_end_time = datetime.now(timezone.utc)
            
            # Infer disconnect reason if not explicitly set
            if session.disconnect_reason is None:
                session.disconnect_reason = "connection_closed"
            
            # Log conversation to Cosmos DB (asynchronous, non-blocking)
            if session.message_pairs:  # Only log if there was actual conversation
                try:
                    from services.conversation_logger import get_conversation_logger
                    conversation_logger = get_conversation_logger()
                    
                    # Log the conversation (fire-and-forget pattern)
                    # Errors in logging won't affect session cleanup
                    success = conversation_logger.log_conversation(session)
                    
                    if success:
                        logger.info(
                            f"Conversation logged for session {session.session_id} "
                            f"({len(session.message_pairs)} messages)"
                        )
                    else:
                        logger.warning(f"Failed to log conversation for session {session.session_id}")
                except Exception as e:
                    logger.error(
                        f"Error logging conversation for session {session.session_id}: {e}",
                        exc_info=True
                    )
                    # Continue with session cleanup even if logging fails
            else:
                logger.debug(f"No messages to log for session {session.session_id}")
        else:
            logger.warning("end_voice_session called but no session found for websocket")
        
        # Always perform cleanup, regardless of logging success/failure
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