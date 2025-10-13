"""Root concierge agent that routes conversations to specialized agents."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

CREDENTIAL = DefaultAzureCredential()
COSMOS_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT")
COSMOS_DATABASE = os.getenv("COSMOSDB_DATABASE")

if not COSMOS_ENDPOINT or not COSMOS_DATABASE:
    logger.warning("Cosmos DB configuration missing for root agent.")

COSMOS_CLIENT = CosmosClient(COSMOS_ENDPOINT, CREDENTIAL)
DATABASE = COSMOS_CLIENT.create_database_if_not_exists(id=COSMOS_DATABASE)
CUSTOMER_CONTAINER = "Customer"
PRODUCT_CONTAINER = "Product"
PRODUCT_URL_CONTAINER = os.getenv("COSMOSDB_ProductUrl_CONTAINER")


def _get_container(name: str):
    """Return a Cosmos container by name."""
    return DATABASE.get_container_client(name)


def get_customer_info(customer_id: str) -> Optional[Dict[str, Any]]:
    """Fetch core customer profile details from Cosmos DB."""
    container = _get_container(CUSTOMER_CONTAINER)
    query = (
        "SELECT c.customer_id, c.first_name, c.last_name, c.email, "
        "c.address.city, c.address.postal_code, c.address.country, "
        "c.phone_number FROM c WHERE c.customer_id = @customer_id"
    )
    try:
        results = list(
            container.query_items(
                query=query,
                parameters=[{"name": "@customer_id", "value": customer_id}],
                enable_cross_partition_query=True,
            )
        )
    except exceptions.CosmosHttpResponseError as exc:
        logger.exception("Failed to fetch customer info")
        return None

    return results[0] if results else None


def get_target_company() -> Optional[str]:
    """Return the primary company name derived from product catalog data."""
    container = _get_container(PRODUCT_CONTAINER)
    try:
        items = list(container.read_all_items())
    except exceptions.CosmosHttpResponseError as exc:
        logger.exception("Failed to read product container")
        return None

    if not items:
        return None

    return items[0].get("company")


def root_assistant(customer_id: str) -> Dict[str, Any]:
    """Return the root agent configuration for the specified customer."""
    company = get_target_company() or "the company"
    customer_profile = get_customer_info(customer_id)
    profile_json = json.dumps(customer_profile, indent=4) if customer_profile else "{}"

    instructions = [
        f"You are a helpful assistant working for the company {company}.",
        "You oversee specialized agents (AI Foundry web search, email, database, and knowledge base).",
        "Keep answers short, professional, and suited for voice interactions.",
        "Always route tasks to the appropriate agent instead of answering directly. Confirm additional questions and close once resolved.",
        "Customer context:\n" + profile_json
    ]

    return {
        "id": "Assistant_Root",
        "name": "Greeter",
        "description": (
            "Handles greetings and routes user requests to specialized agents."
        ),
        "system_message": "\n".join(instructions),
        "tools": [],
    }
