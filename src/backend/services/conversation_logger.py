"""
Conversation Logger Service

Logs AI Agent conversations to Cosmos DB after voice sessions end.
Designed for asynchronous, non-blocking logging to avoid impacting real-time performance.
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

if TYPE_CHECKING:
    from websocket.connection_manager import VoiceSession

logger = logging.getLogger(__name__)

# Azure Cosmos DB configuration
CREDENTIAL = DefaultAzureCredential()
COSMOS_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT")
COSMOS_DATABASE = os.getenv("COSMOSDB_DATABASE")
AI_CONVERSATIONS_CONTAINER = "AI_Conversations"


class ConversationLogger:
    """
    Asynchronously log AI Agent conversations to Cosmos DB.
    
    This service is called at the end of voice sessions to persist
    conversation history, metadata, and session analytics.
    """
    
    def __init__(self):
        """Initialize Cosmos DB client and container."""
        if not COSMOS_ENDPOINT or not COSMOS_DATABASE:
            logger.warning("Cosmos DB configuration is incomplete. Conversation logging disabled.")
            self.enabled = False
            return
        
        try:
            logger.info(f"Initializing ConversationLogger: endpoint={COSMOS_ENDPOINT}, database={COSMOS_DATABASE}")
            self.cosmos_client = CosmosClient(COSMOS_ENDPOINT, CREDENTIAL)
            self.database = self.cosmos_client.get_database_client(COSMOS_DATABASE)
            self.container = self.database.get_container_client(AI_CONVERSATIONS_CONTAINER)
            self.enabled = True
            logger.info("ConversationLogger initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ConversationLogger: {e}")
            self.enabled = False
    
    def log_conversation(self, session: 'VoiceSession') -> bool:
        """
        Log a completed conversation to Cosmos DB.
        
        Args:
            session: The VoiceSession object containing conversation data
            
        Returns:
            bool: True if logging succeeded, False otherwise
        """
        if not self.enabled:
            logger.warning("ConversationLogger is disabled - skipping log")
            return False
        
        # Don't log sessions with no messages
        if not session.message_pairs:
            logger.info(f"Skipping log for session {session.session_id} - no messages")
            return False
        
        try:
            start_time = time.perf_counter()
            
            # Build the conversation document
            document = self._build_document(session)
            
            # Write to Cosmos DB
            self.container.create_item(body=document)
            
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"Logged conversation {session.session_id} to Cosmos DB "
                f"({len(session.message_pairs)} messages, {elapsed:.2f}s)"
            )
            return True
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Cosmos DB error logging conversation {session.session_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to log conversation {session.session_id}: {e}", exc_info=True)
            return False
    
    def _build_document(self, session: 'VoiceSession') -> Dict[str, Any]:
        """
        Build the Cosmos DB document structure from session data.
        
        Args:
            session: The VoiceSession object
            
        Returns:
            dict: Document ready for Cosmos DB insertion
        """
        # Calculate session duration
        duration_seconds = 0
        if session.session_end_time and session.session_start_time:
            duration_seconds = (session.session_end_time - session.session_start_time).total_seconds()
        
        # Build metadata
        metadata = self._build_metadata(session)
        
        # Generate unique document ID
        timestamp = int(time.time() * 1000)  # Milliseconds for uniqueness
        doc_id = f"ai_conv_{session.session_id}_{timestamp}"
        
        # Build the document (aligned with your schema requirements)
        document = {
            "id": doc_id,
            "conversation_id": session.session_id,
            "customer_id": session.customer_id or "anonymous",
            "agent_type": "AI",
            "session_start": session.session_start_time.isoformat() if session.session_start_time else None,
            "session_end": session.session_end_time.isoformat() if session.session_end_time else None,
            "duration_seconds": duration_seconds,
            "disconnect_reason": session.disconnect_reason or "unknown",
            "graceful_disconnect": session.graceful_disconnect,
            "messages": session.message_pairs,  # Already in simplified format (sender, message, interrupted)
            "metadata": metadata
        }
        
        return document
    
    def _build_metadata(self, session: 'VoiceSession') -> Dict[str, Any]:
        """
        Build metadata analytics from conversation data.
        
        Args:
            session: The VoiceSession object
            
        Returns:
            dict: Metadata analytics
        """
        messages = session.message_pairs
        
        # Count messages by sender
        user_messages = sum(1 for m in messages if m.get("sender") == "user")
        assistant_messages = sum(1 for m in messages if m.get("sender") == "assistant")
        
        # Count interruptions
        interruptions = sum(1 for m in messages if m.get("interrupted") == True)
        
        # Track unique agents used (if we track this in the future)
        agents_used = list(set(session.agents_used)) if hasattr(session, 'agents_used') else ["root"]
        
        # Track tools called (if we track this in the future)
        tools_called = list(session.tools_called) if hasattr(session, 'tools_called') else []
        
        metadata = {
            "total_messages": len(messages),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "interruptions": interruptions,
            "agents_used": agents_used,
            "tools_called": tools_called,
            "initial_agent": session.current_agent if hasattr(session, 'current_agent') else "root"
        }
        
        return metadata


# Global singleton instance
_conversation_logger: Optional[ConversationLogger] = None


def get_conversation_logger() -> ConversationLogger:
    """
    Get or create the global ConversationLogger instance.
    
    Returns:
        ConversationLogger: Singleton instance
    """
    global _conversation_logger
    if _conversation_logger is None:
        _conversation_logger = ConversationLogger()
    return _conversation_logger
