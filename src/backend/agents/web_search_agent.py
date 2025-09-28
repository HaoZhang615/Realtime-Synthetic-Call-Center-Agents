"""Web search agent that queries Bing Search for up-to-date information."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import aiohttp
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

BING_API_KEY = os.getenv("BING_SEARCH_API_KEY")
BING_API_ENDPOINT = os.getenv(
    "BING_SEARCH_API_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
)

CREDENTIAL = DefaultAzureCredential()
COSMOS_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT")
COSMOS_DATABASE = os.getenv("COSMOSDB_DATABASE")
PRODUCT_CONTAINER = "Product"
PRODUCT_URL_CONTAINER = os.getenv("COSMOSDB_ProductUrl_CONTAINER")

COSMOS_CLIENT = CosmosClient(COSMOS_ENDPOINT, CREDENTIAL)
DATABASE = COSMOS_CLIENT.create_database_if_not_exists(id=COSMOS_DATABASE)


def _get_target_company() -> str:
    """Return the primary company name from the product catalog."""
    container = DATABASE.get_container_client(PRODUCT_CONTAINER)
    try:
        items = list(container.read_all_items())
    except exceptions.CosmosHttpResponseError as exc:
        logger.exception("Failed to read product collection")
        return ""

    if not items:
        return ""
    return items[0].get("company", "")


async def _load_restricted_urls() -> List[str]:
    """Load URLs from the ProductUrl container to focus Bing queries."""
    if not PRODUCT_URL_CONTAINER:
        return []

    container = DATABASE.get_container_client(PRODUCT_URL_CONTAINER)
    try:
        items = list(
            container.query_items(
                query="SELECT * FROM c", enable_cross_partition_query=True
            )
        )
    except exceptions.CosmosHttpResponseError as exc:
        logger.exception("Failed to read ProductUrl container")
        return []

    if not items:
        return []
    return items[0].get("urls", [])


async def search_web(params: Dict[str, Any]) -> str:
    """Execute a Bing web search and return formatted snippets."""
    if not BING_API_KEY:
        return (
            "Web search is unavailable because no Bing Search API key is "
            "configured."
        )

    query = params.get("query", "")
    if not query:
        return "No search query was provided."

    restricted_urls = await _load_restricted_urls()
    if restricted_urls:
        scopes = " OR ".join(
            f"site:{url.replace('https://', '').replace('http://', '')}"
            for url in restricted_urls
        )
        query = f"{query} {scopes}"

    request_params = {"q": query, "count": 3}
    if params.get("up_to_date"):
        request_params["sortby"] = "Date"

    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            BING_API_ENDPOINT, headers=headers, params=request_params
        ) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientError as exc:
                logger.exception("Bing Search request failed")
                return f"Bing search failed: {exc}"

            payload = await response.json()

    value = payload.get("webPages", {}).get("value", [])
    if not value:
        return "No results found."

    results = []
    for index, item in enumerate(value, start=1):
        snippet = item.get("snippet", "")
        title = item.get("name", "Unknown source")
        url = item.get("url", "")
        results.append(
            f"{index}. content: {snippet}, source_title: {title}, "
            f"source_url: {url}"
        )

    return "\n".join(results)


web_search_agent: Dict[str, Any] = {
    "id": "Assistant_WebSearch",
    "name": "Web Search Agent",
    "description": (
        "Use this agent to retrieve up-to-date information from the web."
    ),
    "system_message": (
        "You query Bing Search to provide current information. Promote the "
        f"offerings of {_get_target_company() or 'the company'} when relevant."
    ),
    "tools": [
        {
            "name": "search_web",
            "description": "Perform a Bing search for relevant information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User request rephrased for search.",
                    },
                    "up_to_date": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether the latest information is required.",
                    },
                },
                "required": ["query"],
            },
            "returns": search_web,
        }
    ],
}
