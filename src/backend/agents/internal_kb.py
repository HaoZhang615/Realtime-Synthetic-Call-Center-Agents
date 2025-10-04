"""Agent responsible for querying the internal Azure AI Search knowledge base."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")

if not _SEARCH_ENDPOINT or not _SEARCH_INDEX:
    logger.warning("[Internal_KB_Agent] Azure AI Search configuration is incomplete.")
else:
    logger.info(
        f"[Internal_KB_Agent] Azure AI Search configured\n"
        f"  Endpoint: {_SEARCH_ENDPOINT}\n"
        f"  Index: {_SEARCH_INDEX}"
    )

_CREDENTIAL = (
    AzureKeyCredential(_ADMIN_KEY)
    if _ADMIN_KEY
    else DefaultAzureCredential()
)

logger.debug("[Internal_KB_Agent] Initializing Azure AI Search client...")
init_start = time.perf_counter()

SEARCH_CLIENT = SearchClient(
    endpoint=_SEARCH_ENDPOINT,
    index_name=_SEARCH_INDEX,
    credential=_CREDENTIAL,
)

init_elapsed = time.perf_counter() - init_start
logger.info(f"[Internal_KB_Agent] Search client initialized in {init_elapsed:.2f}s")


async def query_internal_knowledge_base(params: Dict[str, Any]) -> str:
    """Execute a hybrid search query against the internal knowledge base."""
    start_time = time.perf_counter()
    
    query = params.get("query", "")
    if not query:
        logger.warning("[Internal_KB_Agent] Query request received with empty query")
        return "No query was supplied."

    logger.info(
        f"[Internal_KB_Agent] Starting knowledge base search\n"
        f"  Query: {query}\n"
        f"  Search type: Hybrid (vector + text)\n"
        f"  Top K: 3"
    )

    try:
        # Build vector query
        vector_start = time.perf_counter()
        vector_query = VectorizableTextQuery(
            text=query,
            k_nearest_neighbors=3,
            fields="text_vector",
            exhaustive=True,
        )
        vector_elapsed = time.perf_counter() - vector_start
        logger.debug(f"[Internal_KB_Agent] Vector query prepared in {vector_elapsed:.4f}s")
        
        # Execute search
        search_start = time.perf_counter()
        search_results = SEARCH_CLIENT.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["title", "chunk_id", "chunk"],
            top=3,
        )
        
        # Process results
        sources = []
        result_count = 0
        for document in search_results:
            result_count += 1
            chunk_id = document["chunk_id"]
            page_number = chunk_id.split("_")[-1] if chunk_id else "unknown"
            title = document["title"]
            chunk_preview = document['chunk'][:100]  # First 100 chars
            
            logger.debug(
                f"[Internal_KB_Agent] Result {result_count}: {title} (Page {page_number})\n"
                f"  Chunk preview: {chunk_preview}..."
            )
            
            sources.append(
                f'# Source "{title}" - Page {page_number}\n'
                f"{document['chunk']}"
            )
        
        search_elapsed = time.perf_counter() - search_start
        
        # Build response
        response = "\n".join(sources) if sources else "No relevant documents found."
        total_chars = len(response)
        
        total_elapsed = time.perf_counter() - start_time
        logger.info(
            f"[Internal_KB_Agent] Search completed in {total_elapsed:.2f}s\n"
            f"  Query: {query}\n"
            f"  Search time: {search_elapsed:.2f}s\n"
            f"  Results found: {result_count}\n"
            f"  Response length: {total_chars} characters"
        )
        
        return response
        
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.exception(
            f"[Internal_KB_Agent] Search failed after {elapsed:.2f}s\n"
            f"  Query: {query}\n"
            f"  Error: {exc}"
        )
        return f"Failed to query knowledge base: {exc}"


internal_kb_agent: Dict[str, Any] = {
    "id": "Assistant_internal_kb_agent",
    "name": "Internal Knowledgebase Agent",
    "description": (
        "Call this agent when the user needs information from the internal "
        "knowledge base."
    ),
    "system_message": (
        "You are an internal knowledge base assistant that responds to "
        "questions about the company's knowledge assets. Use "
        "query_internal_knowledge_base to gather precise context."
    ),
    "tools": [
        {
            "name": "query_internal_knowledge_base",
            "description": "Query the internal knowledge base for supporting evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User request rephrased for search.",
                    }
                },
                "required": ["query"],
            },
            "returns": query_internal_knowledge_base,
        }
    ],
}
