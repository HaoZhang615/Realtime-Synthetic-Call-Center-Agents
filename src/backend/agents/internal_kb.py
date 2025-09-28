"""Agent responsible for querying the internal Azure AI Search knowledge base."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

logger = logging.getLogger(__name__)

_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")

if not _SEARCH_ENDPOINT or not _SEARCH_INDEX:
    logger.warning("Azure AI Search configuration is incomplete.")

_CREDENTIAL = (
    AzureKeyCredential(_ADMIN_KEY)
    if _ADMIN_KEY
    else DefaultAzureCredential()
)

SEARCH_CLIENT = SearchClient(
    endpoint=_SEARCH_ENDPOINT,
    index_name=_SEARCH_INDEX,
    credential=_CREDENTIAL,
)


async def query_internal_knowledge_base(params: Dict[str, Any]) -> str:
    """Execute a hybrid search query against the internal knowledge base."""
    query = params.get("query", "")
    if not query:
        return "No query was supplied."

    vector_query = VectorizableTextQuery(
        text=query,
        k_nearest_neighbors=3,
        fields="text_vector",
        exhaustive=True,
    )
    search_results = SEARCH_CLIENT.search(
        search_text=query,
        vector_queries=[vector_query],
        select=["title", "chunk_id", "chunk"],
        top=3,
    )

    sources = []
    for document in search_results:
        chunk_id = document["chunk_id"]
        page_number = chunk_id.split("_")[-1] if chunk_id else "unknown"
        sources.append(
            f'# Source "{document["title"]}" - Page {page_number}\n'
            f"{document['chunk']}"
        )

    return "\n".join(sources)


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
