"""
WebSocket Connection Manager for Realtime Voice Sessions

Manages active WebSocket connections, session state, and cleanup.
Based on patterns from openai-realtime-voice-template but adapted for
multi-agent voice bot architecture.
"""

import logging
import uuid
from typing import Dict, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class VoiceSession:
    """Represents a single voice session with associated state"""
    
    def __init__(self, session_id: str, websocket: WebSocket, customer_id: Optional[str] = None):
        self.session_id = session_id
        self.websocket = websocket
        self.customer_id = customer_id
        self.active = True
        self.current_agent = "root"  # Default to root agent
        self.conversation_items = []
        self.audio_buffer = bytearray()
        
    def __str__(self):
        return f"VoiceSession(id={self.session_id}, customer={self.customer_id}, agent={self.current_agent})"


class WebSocketConnectionManager:
    """
    Manages WebSocket connections for realtime voice communication
    
    Handles connection lifecycle, session management, and broadcasting.
    Designed to work with the existing RealtimeClient architecture.
    """

    def __init__(self):
        # Active connections by session ID
        self.active_connections: Dict[str, VoiceSession] = {}
        # WebSocket to session mapping for quick lookup
        self.websocket_to_session: Dict[WebSocket, str] = {}
        # Sessions by customer ID for customer-specific operations
        self.customer_sessions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, customer_id: Optional[str] = None) -> str:
        """
        Accept a new WebSocket connection and create a session
        
        Returns:
            session_id: Unique identifier for the session
        """
        await websocket.accept()
        
        session_id = str(uuid.uuid4())
        session = VoiceSession(session_id, websocket, customer_id)
        
        self.active_connections[session_id] = session
        self.websocket_to_session[websocket] = session_id
        
        if customer_id:
            if customer_id not in self.customer_sessions:
                self.customer_sessions[customer_id] = set()
            self.customer_sessions[customer_id].add(session_id)
        
        logger.info(f"New voice session connected: {session}")
        return session_id

    async def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection and cleanup
        """
        session_id = self.websocket_to_session.get(websocket)
        if not session_id:
            logger.warning("Attempted to disconnect unknown WebSocket")
            return
            
        session = self.active_connections.get(session_id)
        if session:
            logger.info(f"Voice session disconnected: {session}")
            
            # Cleanup customer session mapping
            if session.customer_id:
                customer_sessions = self.customer_sessions.get(session.customer_id, set())
                customer_sessions.discard(session_id)
                if not customer_sessions:
                    del self.customer_sessions[session.customer_id]
            
            # Mark session as inactive and remove
            session.active = False
            del self.active_connections[session_id]
            del self.websocket_to_session[websocket]

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get session by ID"""
        return self.active_connections.get(session_id)

    def get_session_by_websocket(self, websocket: WebSocket) -> Optional[VoiceSession]:
        """Get session by WebSocket"""
        session_id = self.websocket_to_session.get(websocket)
        return self.active_connections.get(session_id) if session_id else None

    def get_customer_sessions(self, customer_id: str) -> Set[VoiceSession]:
        """Get all active sessions for a customer"""
        session_ids = self.customer_sessions.get(customer_id, set())
        return {
            self.active_connections[sid] 
            for sid in session_ids 
            if sid in self.active_connections
        }

    async def send_to_session(self, session_id: str, message: str) -> bool:
        """
        Send message to a specific session
        
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        session = self.active_connections.get(session_id)
        if not session or not session.active:
            return False
            
        try:
            await session.websocket.send_text(message)
            return True
        except Exception as e:
            logger.exception(f"Failed to send message to session {session_id}: {e}")
            await self.disconnect(session.websocket)
            return False

    async def send_to_customer(self, customer_id: str, message: str) -> int:
        """
        Send message to all sessions for a customer
        
        Returns:
            int: Number of sessions message was sent to
        """
        sessions = self.get_customer_sessions(customer_id)
        success_count = 0
        
        for session in sessions:
            if await self.send_to_session(session.session_id, message):
                success_count += 1
                
        return success_count

    async def broadcast(self, message: str, exclude_session: Optional[str] = None) -> int:
        """
        Broadcast message to all active sessions
        
        Returns:
            int: Number of sessions message was sent to
        """
        success_count = 0
        
        for session_id, session in self.active_connections.items():
            if exclude_session and session_id == exclude_session:
                continue
                
            if await self.send_to_session(session_id, message):
                success_count += 1
                
        return success_count

    def get_connection_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "customers_connected": len(self.customer_sessions),
            "sessions_by_agent": self._get_agent_stats(),
        }
        
    def _get_agent_stats(self) -> dict:
        """Get session count by current agent"""
        agent_stats = {}
        for session in self.active_connections.values():
            agent = session.current_agent
            agent_stats[agent] = agent_stats.get(agent, 0) + 1
        return agent_stats


# Global connection manager instance
connection_manager = WebSocketConnectionManager()