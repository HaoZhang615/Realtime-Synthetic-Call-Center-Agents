"""AI Foundry Web Search Agent using MCP Server."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def web_search_agent() -> Dict[str, Any]:
    """
    Return the AI Foundry web search agent configuration.
    
    This agent performs web searches using Azure AI Foundry Agent
    with Bing grounding via the MCP server.
    """
    instructions = [
        "You are a web search specialist powered by Azure AI Foundry with Bing Search.",
        "You have access to real-time web search capabilities through Bing.",
        "When users ask questions requiring current information, web searches, or real-time data:",
        "- Use the search_web_ai_foundry tool to find accurate, up-to-date information",
        "- Synthesize search results into clear, concise answers",
        "- Cite sources when providing specific facts or data",
        "- If search results are inconclusive, acknowledge limitations honestly",
        "For tasks outside web search, route back to the root agent.",
        "Keep responses conversational and suitable for voice interactions."
    ]
    
    return {
        "id": "Assistant_WebSearch",
        "name": "Web Search Specialist",
        "description": (
            "Performs real-time web searches using Azure AI Foundry Agent with Bing Search. "
            "Use this agent for: current events, weather, stock prices, news, research, "
            "factual lookups, or any question requiring up-to-date information from the web."
        ),
        "system_message": "\n".join(instructions),
        "tools": [
            {
                "type": "function",
                "name": "search_web_ai_foundry",
                "description": (
                    "Search the web using Azure AI Foundry Agent with Bing Search. "
                    "Returns comprehensive, AI-synthesized results from current web sources. "
                    "Use for: weather, news, current events, facts, research, or any real-time information."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The search query. Be specific and include relevant context. "
                                "Examples: 'weather in Seattle today', 'latest news about AI', "
                                "'stock price of Microsoft'"
                            ),
                        }
                    },
                    "required": ["query"],
                },
                "returns": "search_web_ai_foundry",  # This will be resolved to the async method
            }
        ],
    }
