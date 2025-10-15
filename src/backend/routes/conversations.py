"""
Conversation API routes for retrieving conversation history from CosmosDB
"""

import logging
import os
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
from load_azd_env import load_azd_environment

# Load environment
load_azd_environment()

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Cosmos DB client
try:
    credential = DefaultAzureCredential()
    cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
    cosmos_database = os.getenv("COSMOSDB_DATABASE")
    
    if not cosmos_endpoint or not cosmos_database:
        logger.warning("Cosmos DB configuration missing")
        cosmos_client = None
    else:
        cosmos_client = CosmosClient(cosmos_endpoint, credential)
        database = cosmos_client.get_database_client(cosmos_database)
        ai_conversations_container = database.get_container_client("AI_Conversations")
except Exception as e:
    logger.error(f"Failed to initialize Cosmos DB client: {e}")
    cosmos_client = None
    database = None
    ai_conversations_container = None


class ConversationSummary(BaseModel):
    """Summary of a conversation for list display"""
    id: str
    conversation_id: str
    title: Optional[str] = None
    session_start: Optional[str]
    session_end: Optional[str]
    duration_seconds: float
    message_count: int
    first_message_preview: str


class ConversationDetail(BaseModel):
    """Full conversation details"""
    id: str
    conversation_id: str
    customer_id: str
    agent_type: str
    session_start: Optional[str]
    session_end: Optional[str]
    duration_seconds: float
    disconnect_reason: str
    graceful_disconnect: bool
    messages: List[Dict]
    metadata: Dict


@router.get("/conversations/{customer_id}", response_model=List[ConversationSummary])
async def get_customer_conversations(
    customer_id: str,
    limit: int = Query(default=20, le=100, description="Maximum number of conversations to return")
):
    """
    Get conversation history for a specific customer.
    Returns a list of conversation summaries ordered by most recent first.
    """
    if not ai_conversations_container:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured")
    
    try:
        # Query conversations for this customer, ordered by session_start descending
        query = """
        SELECT 
            c.id,
            c.conversation_id,
            c.title,
            c.session_start,
            c.session_end,
            c.duration_seconds,
            c.messages,
            c.metadata
        FROM c 
        WHERE c.customer_id = @customer_id
        ORDER BY c.session_start DESC
        OFFSET 0 LIMIT @limit
        """
        
        parameters = [
            {"name": "@customer_id", "value": customer_id},
            {"name": "@limit", "value": limit}
        ]
        
        conversations = list(ai_conversations_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=False,  # We're partitioning by customer_id
            partition_key=customer_id
        ))
        
        # Transform to summaries
        summaries = []
        for conv in conversations:
            messages = conv.get("messages", [])
            message_count = len(messages)
            
            # Get first user message as preview
            first_message = ""
            for msg in messages:
                if msg.get("sender") == "user" and msg.get("message"):
                    first_message = msg["message"]
                    break
            
            # Truncate preview
            if len(first_message) > 80:
                first_message = first_message[:77] + "..."
            
            summaries.append(ConversationSummary(
                id=conv["id"],
                conversation_id=conv["conversation_id"],
                title=conv.get("title"),
                session_start=conv.get("session_start"),
                session_end=conv.get("session_end"),
                duration_seconds=conv.get("duration_seconds", 0),
                message_count=message_count,
                first_message_preview=first_message or "(No messages)"
            ))
        
        return summaries
        
    except exceptions.CosmosHttpResponseError as e:
        logger.error(f"Cosmos DB error fetching conversations for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        logger.error(f"Error fetching conversations for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{customer_id}/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_detail(customer_id: str, conversation_id: str):
    """
    Get full details of a specific conversation.
    """
    if not ai_conversations_container:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured")
    
    try:
        # Query for the specific conversation
        query = """
        SELECT * FROM c 
        WHERE c.customer_id = @customer_id 
        AND c.conversation_id = @conversation_id
        """
        
        parameters = [
            {"name": "@customer_id", "value": customer_id},
            {"name": "@conversation_id", "value": conversation_id}
        ]
        
        results = list(ai_conversations_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=False,
            partition_key=customer_id
        ))
        
        if not results:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conv = results[0]
        
        return ConversationDetail(
            id=conv["id"],
            conversation_id=conv["conversation_id"],
            customer_id=conv["customer_id"],
            agent_type=conv.get("agent_type", "AI"),
            session_start=conv.get("session_start"),
            session_end=conv.get("session_end"),
            duration_seconds=conv.get("duration_seconds", 0),
            disconnect_reason=conv.get("disconnect_reason", "unknown"),
            graceful_disconnect=conv.get("graceful_disconnect", False),
            messages=conv.get("messages", []),
            metadata=conv.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except exceptions.CosmosHttpResponseError as e:
        logger.error(f"Cosmos DB error fetching conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{customer_id}/{document_id}")
async def delete_conversation(customer_id: str, document_id: str):
    """
    Delete a specific conversation document.
    """
    if not ai_conversations_container:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured")
    
    try:
        # Delete the document by id and partition key
        ai_conversations_container.delete_item(
            item=document_id,
            partition_key=customer_id
        )
        
        logger.info(f"Deleted conversation {document_id} for customer {customer_id}")
        return {"success": True, "message": "Conversation deleted successfully"}
        
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except exceptions.CosmosHttpResponseError as e:
        logger.error(f"Cosmos DB error deleting conversation {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        logger.error(f"Error deleting conversation {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

