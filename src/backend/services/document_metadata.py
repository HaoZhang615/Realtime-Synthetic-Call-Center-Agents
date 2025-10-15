"""Service to extract document topics from AI Search index metadata."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Set

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

logger = logging.getLogger(__name__)

# Azure AI Search configuration
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX") or os.getenv("AZURE_SEARCH_INDEX_NAME") or "sample-index"
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")

# Initialize search client
if AZURE_SEARCH_KEY:
    search_credential = AzureKeyCredential(AZURE_SEARCH_KEY)
else:
    search_credential = DefaultAzureCredential()

search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX,
    credential=search_credential
)


def extract_topics_from_headers(header_text: str) -> List[str]:
    """
    Extract meaningful topic keywords from a header string.
    
    Args:
        header_text: Header text (e.g., "Employee Benefits and Compensation")
        
    Returns:
        List of topic keywords
    """
    if not header_text:
        return []
    
    # Clean and normalize
    header_text = header_text.strip().lower()
    
    # Remove common filler words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'about'
    }
    
    # Split on common delimiters
    import re
    words = re.split(r'[,;&\-\|/]|\s+', header_text)
    
    # Filter and clean
    topics = []
    for word in words:
        word = word.strip()
        if word and word not in stop_words and len(word) > 2:
            topics.append(word)
    
    return topics


def get_all_document_topics() -> List[str]:
    """
    Retrieve all unique topics from AI Search index metadata.
    
    Extracts topics from document titles and headers (h1, h2).
    
    NOTE: Top 100 limit is set intentionally low for demo purposes.
    Increase this value for production use based on your document volume.
    
    Returns:
        Sorted list of unique topic strings
    """
    try:
        logger.info("Extracting topics from AI Search index metadata")
        
        # Query all documents, selecting only metadata fields
        # NOTE: top=100 is set low for demo purposes - increase for production
        results = search_client.search(
            search_text="*",
            select=["title", "header_1", "header_2"],  # Only h1 and h2 for now
            top=100,  # Limited for demo - increase based on document volume
            include_total_count=True
        )
        
        topics_set: Set[str] = set()
        unique_titles: Set[str] = set()
        doc_count = 0
        
        for doc in results:
            doc_count += 1
            
            # Extract title (without extension)
            title = doc.get("title", "")
            if title:
                # Remove file extension
                title_clean = title.rsplit(".", 1)[0] if "." in title else title
                unique_titles.add(title_clean)
                # Extract topics from title
                topics_set.update(extract_topics_from_headers(title_clean))
            
            # Extract from headers (only h1 and h2)
            for header_field in ["header_1", "header_2"]:
                header = doc.get(header_field, "")
                if header:
                    # Add full header as a topic
                    topics_set.add(header.lower().strip())
                    # Also extract individual keywords from header
                    topics_set.update(extract_topics_from_headers(header))
        
        # Combine document titles and extracted topics
        all_topics = list(unique_titles.union(topics_set))
        
        # Sort and limit to reasonable size
        all_topics.sort()
        
        logger.info(
            f"Extracted {len(all_topics)} unique topics from {doc_count} document chunks "
            f"({len(unique_titles)} unique documents)"
        )
        
        return all_topics
        
    except Exception as e:
        logger.error(f"Failed to extract topics from AI Search index: {e}")
        return []


def get_document_summaries() -> List[Dict[str, Any]]:
    """
    Get a summary of all indexed documents with their topics.
    
    Returns:
        List of dictionaries with document metadata
    """
    try:
        # Aggregate by document title
        # NOTE: top=100 is set low for demo purposes
        results = search_client.search(
            search_text="*",
            select=["title", "header_1", "header_2"],
            top=100
        )
        
        # Group by title
        docs_by_title: Dict[str, Dict[str, Set[str]]] = {}
        
        for doc in results:
            title = doc.get("title", "Unknown")
            if title not in docs_by_title:
                docs_by_title[title] = {
                    "title": title,
                    "headers": set()
                }
            
            # Collect all unique headers for this document
            for header_field in ["header_1", "header_2"]:
                header = doc.get(header_field, "")
                if header:
                    docs_by_title[title]["headers"].add(header)
        
        # Convert to list format
        summaries = []
        for doc_data in docs_by_title.values():
            summaries.append({
                "title": doc_data["title"],
                "topics": sorted(list(doc_data["headers"]))[:10]  # Top 10 headers
            })
        
        return summaries
        
    except Exception as e:
        logger.error(f"Failed to get document summaries: {e}")
        return []


def get_kb_agent_description() -> str:
    """
    Generate dynamic description for Internal KB agent based on indexed document metadata.
    
    This function queries the AI Search index in real-time to get current topics,
    ensuring the description stays up-to-date even when documents are deleted.
    
    Returns:
        Description string with current topics from AI Search index
    """
    summaries = get_document_summaries()
    
    if not summaries:
        return (
            "Call this agent when the user needs information from the internal "
            "knowledge base or company documentation."
        )
    
    # Build a clean description using document titles and their main topics
    doc_descriptions = []
    
    for doc_summary in summaries[:5]:  # Limit to first 5 documents for brevity
        title = doc_summary["title"]
        topics = doc_summary["topics"]
        
        # Clean up title (remove extension and path)
        title_clean = title.rsplit(".", 1)[0] if "." in title else title
        title_clean = title_clean.replace("_", " ").replace("-", " ")
        
        if topics:
            # Use top 3 topics for each document
            topic_preview = ", ".join(topics[:3])
            if len(topics) > 3:
                topic_preview += "..."
            doc_descriptions.append(f"{title_clean} ({topic_preview})")
        else:
            doc_descriptions.append(title_clean)
    
    # Create the description
    if len(summaries) > 5:
        doc_list = "; ".join(doc_descriptions) + f" (and {len(summaries) - 5} more documents)"
    else:
        doc_list = "; ".join(doc_descriptions)
    
    return (
        f"Call this agent when the user asks about topics covered in: {doc_list}. "
        f"This agent searches the company's internal knowledge base and documentation."
    )
