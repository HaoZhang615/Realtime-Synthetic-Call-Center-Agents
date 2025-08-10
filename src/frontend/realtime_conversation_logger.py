import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import uuid4
import os
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
import util

logger = logging.getLogger(__name__)

class RealtimeConversationLogger:
    """
    Conversation logger optimized for realtime voice interactions.
    
    Features:
    - Non-blocking buffered logging
    - Periodic batch saves to reduce CosmosDB calls
    - Handles interruptions gracefully
    - Async operations to maintain low latency
    """
    
    def __init__(self, customer_id: str, session_id: str = None):
        self.customer_id = customer_id
        self.session_id = session_id or str(uuid4())
        self.conversation_id = f"{customer_id}_{self.session_id}_{int(datetime.now().timestamp())}"
        
        # Message buffer for batching
        self.message_buffer: List[Dict] = []
        self.buffer_lock = asyncio.Lock()
        
        # Transcription accumulation for assistant messages only
        self.current_assistant_transcription = ""
        self.transcription_lock = asyncio.Lock()
        
        # Conversation document
        self.conversation_doc = self._create_conversation_document()
        
        # Auto-save settings
        self.auto_save_interval = 10.0  # Save every 10 seconds
        self.buffer_size_limit = 5      # Or when buffer reaches 5 messages
        self.last_save_time = datetime.now()
        
        # Background task
        self._save_task = None
        self._shutdown = False
        
        # Initialize CosmosDB
        self._setup_cosmos_client()
        
    def _setup_cosmos_client(self):
        """Initialize CosmosDB client using the same pattern as backend."""
        try:
            util.load_dotenv_from_azd()
            credential = DefaultAzureCredential()
            
            cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
            database_name = os.getenv("COSMOSDB_DATABASE")
            container_name = os.getenv("COSMOSDB_AIConversations_CONTAINER")
            
            self.cosmos_client = CosmosClient(cosmos_endpoint, credential)
            self.database = self.cosmos_client.get_database_client(database_name)
            self.container = self.database.get_container_client(container_name)
            
            logger.info(f"Realtime logger connected to CosmosDB container: {container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize CosmosDB for realtime logger: {e}")
            self.container = None
    
    def _create_conversation_document(self) -> Dict:
        """Create the base conversation document."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": self.conversation_id,
            "customer_id": self.customer_id,
            "session_id": self.session_id,
            "created_at": now,
            "updated_at": now,
            "voicebot": "realtime",
            "messages": [],
            "metadata": {
                "interruptions": 0,
                "total_messages": 0,
                "session_duration_ms": 0,
                "last_activity": now
            }
        }
    
    async def start_logging(self):
        """Start the background auto-save task."""
        if self._save_task is None and not self._shutdown:
            self._save_task = asyncio.create_task(self._auto_save_loop())
            logger.info("Started realtime conversation logging")
    
    async def stop_logging(self):
        """Stop logging and perform final save."""
        self._shutdown = True
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        
        # Final save of any buffered messages
        await self._save_buffered_messages(force=True)
        logger.info("Stopped realtime conversation logging")
    
    async def log_user_message(self, content: str, message_type: str = "text", metadata: Dict = None):
        """Log user message to buffer."""
        await self._add_message_to_buffer("user", content, message_type, metadata)
    
    async def log_interruption(self):
        """Log when user interrupts assistant."""
        self.conversation_doc["metadata"]["interruptions"] += 1
        logger.info(f"User interruption #{self.conversation_doc['metadata']['interruptions']} logged")
        
        # Clear any accumulated assistant transcription since it was interrupted
        async with self.transcription_lock:
            if self.current_assistant_transcription.strip():
                logger.info(f"Clearing interrupted assistant transcription: '{self.current_assistant_transcription.strip()}'")
                self.current_assistant_transcription = ""
    
    async def accumulate_assistant_transcription(self, transcription_fragment: str):
        """Accumulate assistant transcription fragments (don't log yet)."""
        async with self.transcription_lock:
            self.current_assistant_transcription += transcription_fragment
            logger.debug(f"Assistant transcription accumulated: '{transcription_fragment}' -> Total: '{self.current_assistant_transcription}'")
    
    async def finalize_assistant_transcription(self):
        """Finalize and log complete assistant transcription."""
        async with self.transcription_lock:
            if self.current_assistant_transcription.strip():
                logger.info(f"Finalizing assistant transcription: '{self.current_assistant_transcription.strip()}'")
                await self._add_message_to_buffer("assistant", self.current_assistant_transcription.strip(), "audio")
                self.current_assistant_transcription = ""
    
    async def _add_message_to_buffer(self, role: str, content: str, message_type: str = "text", metadata: Dict = None):
        """Add message to buffer for batched saving."""
        async with self.buffer_lock:
            message = {
                "role": role,
                "content": content,
                "message_type": message_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {}
            }
            
            self.message_buffer.append(message)
            self.conversation_doc["metadata"]["total_messages"] += 1
            self.conversation_doc["metadata"]["last_activity"] = message["timestamp"]
            
            # Trigger save if buffer is full
            if len(self.message_buffer) >= self.buffer_size_limit:
                asyncio.create_task(self._save_buffered_messages())
    
    async def _auto_save_loop(self):
        """Background task for periodic saves."""
        try:
            while not self._shutdown:
                await asyncio.sleep(self.auto_save_interval)
                if not self._shutdown:
                    await self._save_buffered_messages()
        except asyncio.CancelledError:
            logger.info("Auto-save loop cancelled")
    
    async def _save_buffered_messages(self, force: bool = False):
        """Save buffered messages to CosmosDB."""
        if not self.container:
            logger.warning("CosmosDB not available, skipping save")
            return
            
        async with self.buffer_lock:
            if not self.message_buffer and not force:
                return
                
            # Move messages from buffer to conversation document
            if self.message_buffer:
                self.conversation_doc["messages"].extend(self.message_buffer)
                message_count = len(self.message_buffer)
                self.message_buffer.clear()
                
                # Update conversation metadata
                self.conversation_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                
                # Calculate session duration
                created_time = datetime.fromisoformat(self.conversation_doc["created_at"].replace('Z', '+00:00'))
                current_time = datetime.now(timezone.utc)
                duration_ms = int((current_time - created_time).total_seconds() * 1000)
                self.conversation_doc["metadata"]["session_duration_ms"] = duration_ms
                
                try:
                    # Async upsert to CosmosDB
                    await asyncio.get_event_loop().run_in_executor(
                        None, 
                        self.container.upsert_item, 
                        self.conversation_doc
                    )
                    logger.debug(f"Saved {message_count} messages to CosmosDB (conversation: {self.conversation_id})")
                except Exception as e:
                    logger.error(f"Failed to save conversation to CosmosDB: {e}")
                    # Re-add messages to buffer for retry
                    self.message_buffer.extend(self.conversation_doc["messages"][-message_count:])
                    self.conversation_doc["messages"] = self.conversation_doc["messages"][:-message_count]
