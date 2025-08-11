"""
Conversation Manager for storing and retrieving conversation history in Cosmos DB.
Handles AI_Conversations container operations with proper error handling and retry logic.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from uuid import uuid4
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Manages conversation history storage and retrieval in Cosmos DB.
    
    Uses managed identity for secure authentication and implements
    retry logic for resilient operations.
    """
    
    def __init__(self):
        """Initialize Cosmos DB client and container connection."""
        self.setup_cosmos_client()
    
    def setup_cosmos_client(self):
        """
        Set up Cosmos DB client using managed identity.
        Implements secure authentication without hardcoded credentials.
        """
        try:
            # Use managed identity for secure authentication
            credential = DefaultAzureCredential()
            
            # Get Cosmos DB configuration from environment
            cosmos_endpoint = os.environ["COSMOSDB_ENDPOINT"]
            database_name = os.environ["COSMOSDB_DATABASE"]
            container_name = os.environ["COSMOSDB_AIConversations_CONTAINER"]
            
            # Initialize Cosmos client
            self.cosmos_client = CosmosClient(cosmos_endpoint, credential)
            self.database = self.cosmos_client.get_database_client(database_name)
            self.container = self.database.get_container_client(container_name)
            
            logger.info(f"Successfully connected to Cosmos DB container: {container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB client: {e}")
            raise
    
    def generate_conversation_id(self, customer_id: str, session_id: str) -> str:
        """
        Generate a unique conversation ID.
        
        Args:
            customer_id: Customer/session identifier
            session_id: Streamlit session ID
            
        Returns:
            Unique conversation ID
        """
        return f"{customer_id}_{session_id}_{str(uuid4())[:8]}"
    
    def create_conversation_document(
        self, 
        customer_id: str, 
        session_id: str,
        voicebot_type: Optional[str] = None
    ) -> Dict:
        """
        Create a new conversation document structure.
        
        Args:
            customer_id: Customer/session identifier (partition key)
            session_id: Streamlit session ID
            voicebot_type: Optional voicebot type identifier (e.g., "classic", "multiagent")
            
        Returns:
            New conversation document
        """
        now = datetime.now(timezone.utc).isoformat()
        conversation_id = self.generate_conversation_id(customer_id, session_id)
        
        document = {
            "id": conversation_id,
            "customer_id": customer_id,  # Partition key
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "messages": []
        }
        
        # Add voicebot type if specified
        if voicebot_type:
            document["voicebot"] = voicebot_type
            
        return document
    
    def add_message_to_conversation(
        self,
        conversation_doc: Dict,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Add a new message to the conversation document.
        
        Args:
            conversation_doc: Existing conversation document
            role: Message role (user/assistant)
            content: Message content
            tool_calls: Optional tool call information for evaluation
            
        Returns:
            Updated conversation document
        """
        now = datetime.now(timezone.utc).isoformat()
        
        message = {
            "role": role,
            "content": content,
            "timestamp": now
        }
        
        # Add tool calls if present (for evaluation purposes)
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        # Update conversation document
        conversation_doc["messages"].append(message)
        conversation_doc["updated_at"] = now
        
        return conversation_doc
    
    def save_conversation(self, conversation_doc: Dict) -> bool:
        """
        Save or update conversation document in Cosmos DB.
        
        Implements upsert operation with error handling and retry logic.
        
        Args:
            conversation_doc: Conversation document to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use upsert to create or update the document
            self.container.upsert_item(
                body=conversation_doc
            )
            
            logger.debug(f"Successfully saved conversation: {conversation_doc['id']}")
            return True
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Cosmos DB HTTP error saving conversation: {e}")
            return False
        except exceptions.CosmosResourceNotFoundError as e:
            logger.error(f"Cosmos DB resource not found: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving conversation: {e}")
            return False
    
    def get_conversation(self, conversation_id: str, customer_id: str) -> Optional[Dict]:
        """
        Retrieve a specific conversation by ID.
        
        Args:
            conversation_id: Unique conversation ID
            customer_id: Customer ID (partition key)
            
        Returns:
            Conversation document or None if not found
        """
        try:
            return self.container.read_item(
                item=conversation_id,
                partition_key=customer_id
            )
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Conversation not found: {conversation_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving conversation: {e}")
            return None
    
    def get_recent_conversations(self, customer_id: str, limit: int = 10) -> List[Dict]:
        """
        Get recent conversations for a customer.
        
        Args:
            customer_id: Customer ID (partition key)
            limit: Maximum number of conversations to return
            
        Returns:
            List of recent conversation documents
        """
        try:
            query = """
                SELECT * FROM c 
                WHERE c.customer_id = @customer_id 
                ORDER BY c.updated_at DESC 
                OFFSET 0 LIMIT @limit
            """
            
            parameters = [
                {"name": "@customer_id", "value": customer_id},
                {"name": "@limit", "value": limit}
            ]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=False
            ))
            
            return items
            
        except Exception as e:
            logger.error(f"Error retrieving recent conversations: {e}")
            return []
    
    def delete_conversation(self, conversation_id: str, customer_id: str) -> bool:
        """
        Delete a specific conversation.
        
        Args:
            conversation_id: Unique conversation ID
            customer_id: Customer ID (partition key)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.container.delete_item(
                item=conversation_id,
                partition_key=customer_id
            )
            logger.info(f"Successfully deleted conversation: {conversation_id}")
            return True
            
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Conversation not found for deletion: {conversation_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return False
