"""Database agent that provides Cosmos DB interactions for the assistant."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

# Azure Cosmos DB configuration
CREDENTIAL = DefaultAzureCredential()
COSMOS_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT")
COSMOS_DATABASE = os.getenv("COSMOSDB_DATABASE")

if not COSMOS_ENDPOINT or not COSMOS_DATABASE:
    logger.warning("Cosmos DB configuration is incomplete.")

COSMOS_CLIENT = CosmosClient(COSMOS_ENDPOINT, CREDENTIAL)
DATABASE = COSMOS_CLIENT.create_database_if_not_exists(id=COSMOS_DATABASE)
CUSTOMER_CONTAINER = "Customer"
PURCHASE_CONTAINER = "Purchases"
PRODUCT_CONTAINER = "Product"


class DatabaseAgent:
    """Encapsulates database operations scoped to a single customer."""

    def __init__(self, customer_id: str) -> None:
        self.customer_id = customer_id

    def _get_container(self, container_name: str):
        """Return a Cosmos container client by name."""
        return DATABASE.get_container_client(container_name)

    def validate_customer_exists(self) -> bool:
        """Return True if the customer exists in the Customer container."""
        container = self._get_container(CUSTOMER_CONTAINER)
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.customer_id = @customer_id"
        parameters = [{"name": "@customer_id", "value": self.customer_id}]
        result = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        return result[0] > 0 if result else False

    def _derive_product_id(self, purchase_record: Dict[str, Any]) -> Optional[str]:
        """Derive a product identifier from the purchase payload."""
        container = self._get_container(PRODUCT_CONTAINER)
        product_name = purchase_record.get("product_name")
        if not product_name:
            return None

        query = "SELECT TOP 1 * FROM c WHERE CONTAINS(c.name, @name)"
        params = [{"name": "@name", "value": product_name}]
        results = list(
            container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        if results:
            purchase_record["product_id"] = results[0]["product_id"]
            purchase_record.pop("product_name", None)
            return purchase_record["product_id"]
        return None

    def create_purchases_record(self, parameters: Dict[str, Any]) -> str:
        """Create a purchase record for the current customer."""
        purchase_record = parameters.get("purchase_record", {})
        if "product_id" not in purchase_record:
            if "product_id" in parameters:
                purchase_record["product_id"] = parameters["product_id"]
            elif not self._derive_product_id(purchase_record):
                return (
                    "Product details are missing. Provide a product_id or a "
                    "product_name that can be resolved."
                )

        if not self.validate_customer_exists():
            return f"Customer with ID {self.customer_id} not found."

        product_details = self._load_product_details(purchase_record["product_id"])
        if not product_details:
            return (
                f"Product with ID {purchase_record['product_id']} could not "
                "be found."
            )

        quantity = purchase_record.get("quantity", 1)
        container = self._get_container(PURCHASE_CONTAINER)
        final_record = {
            "customer_id": self.customer_id,
            "product_id": purchase_record["product_id"],
            "quantity": quantity,
            "purchasing_date": datetime.now(timezone.utc).isoformat(),
            "delivered_date": (
                datetime.now(timezone.utc) + timedelta(days=5)
            ).isoformat(),
            "order_number": uuid.uuid4().hex,
            "product_details": product_details,
            "total_price": product_details.get("unit_price", 0) * quantity,
            "id": str(uuid.uuid4()),
        }

        try:
            container.create_item(body=final_record)
        except exceptions.CosmosHttpResponseError as exc:
            logger.exception("Failed to create purchase record")
            return f"Failed to create purchase record: {exc}"
        return "Purchase record created successfully."

    def _load_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Return product metadata for the supplied product identifier."""
        container = self._get_container(PRODUCT_CONTAINER)
        query = "SELECT * FROM c WHERE c.product_id = @product_id"
        params = [{"name": "@product_id", "value": product_id}]
        results = list(
            container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        if not results:
            return None

        product = results[0]
        return {
            "name": product.get("name"),
            "category": product.get("category"),
            "type": product.get("type"),
            "brand": product.get("brand"),
            "company": product.get("company"),
            "unit_price": product.get("unit_price"),
            "weight": product.get("weight"),
            "color": product.get("color", ""),
            "material": product.get("material", ""),
        }

    def update_customer_record(self, parameters: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Update the customer's record with permitted fields."""
        container = self._get_container(CUSTOMER_CONTAINER)
        query = "SELECT * FROM c WHERE c.customer_id = @customer_id"
        items = list(
            container.query_items(
                query=query,
                parameters=[{"name": "@customer_id", "value": self.customer_id}],
                enable_cross_partition_query=True,
            )
        )
        if not items:
            return "Customer record not found."

        customer_doc = items[0]
        allowed_fields = {
            "first_name",
            "last_name",
            "email",
            "address",
            "phone_number",
        }
        updates = {k: v for k, v in parameters.items() if k in allowed_fields}
        customer_doc.update(updates)

        try:
            container.replace_item(item=customer_doc, body=customer_doc)
        except exceptions.CosmosHttpResponseError as exc:
            logger.exception("Failed to update customer record")
            return f"Failed to update customer record: {exc}"

        return {
            "status": "success",
            "message": "Customer record updated successfully.",
        }

    def get_customer_record(self, parameters: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Return the customer profile for the active customer."""
        container = self._get_container(CUSTOMER_CONTAINER)
        query = (
            "SELECT c.customer_id, c.first_name, c.last_name, c.email, "
            "c.address, c.phone_number FROM c WHERE c.customer_id = @customer_id"
        )
        try:
            items = list(
                container.query_items(
                    query=query,
                    parameters=[
                        {"name": "@customer_id", "value": self.customer_id}
                    ],
                    enable_cross_partition_query=True,
                )
            )
        except exceptions.CosmosHttpResponseError as exc:
            logger.exception("Failed to retrieve customer record")
            return f"Failed to get customer record: {exc}"

        if not items:
            return f"No customer found with ID: {self.customer_id}."
        return items[0]

    def get_product_record(self, parameters: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any], str]:
        """Return product metadata or a specific product lookup."""
        container = self._get_container(PRODUCT_CONTAINER)
        try:
            if "product_id" in parameters:
                query = (
                    "SELECT c.product_id, c.name, c.category, c.type, c.brand, "
                    "c.company, c.unit_price, c.weight FROM c "
                    "WHERE c.product_id = @product_id"
                )
                items = list(
                    container.query_items(
                        query=query,
                        parameters=[
                            {
                                "name": "@product_id",
                                "value": parameters["product_id"],
                            }
                        ],
                        enable_cross_partition_query=True,
                    )
                )
                if not items:
                    return (
                        f"No product found with ID: {parameters['product_id']}."
                    )
                return items[0]

            items = list(container.read_all_items())
            return items if items else "No products found."
        except exceptions.CosmosHttpResponseError as exc:
            logger.exception("Failed to retrieve product records")
            return f"Failed to get product record(s): {exc}"

    def get_purchases_record(self, parameters: Dict[str, Any]) -> Union[List[Dict[str, Any]], str]:
        """Return enriched purchase history for the active customer."""
        if not self.validate_customer_exists():
            return f"Customer with ID {self.customer_id} not found."

        purchase_container = self._get_container(PURCHASE_CONTAINER)
        product_container = self._get_container(PRODUCT_CONTAINER)
        query = (
            "SELECT c.customer_id, c.product_id, c.quantity, c.purchasing_date, "
            "c.delivered_date, c.order_number, c.total_price FROM c "
            "WHERE c.customer_id = @customer_id"
        )
        try:
            purchases = list(
                purchase_container.query_items(
                    query=query,
                    parameters=[
                        {"name": "@customer_id", "value": self.customer_id}
                    ],
                    enable_cross_partition_query=True,
                )
            )
        except exceptions.CosmosHttpResponseError as exc:
            logger.exception("Failed to retrieve purchase records")
            return f"Failed to get purchase records: {exc}"

        if not purchases:
            return f"No purchases found for customer: {self.customer_id}."

        enhanced: List[Dict[str, Any]] = []
        for purchase in purchases:
            product = list(
                product_container.query_items(
                    query=(
                        "SELECT c.name, c.category, c.type, c.brand, c.company, "
                        "c.unit_price, c.weight FROM c WHERE c.product_id = @pid"
                    ),
                    parameters=[
                        {"name": "@pid", "value": purchase["product_id"]}
                    ],
                    enable_cross_partition_query=True,
                )
            )
            product_info = (
                {
                    "name": product[0].get("name"),
                    "category": product[0].get("category"),
                    "type": product[0].get("type"),
                    "brand": product[0].get("brand"),
                    "company": product[0].get("company"),
                    "price": product[0].get("unit_price"),
                    "weight": product[0].get("weight"),
                }
                if product
                else {"error": "Product details not found."}
            )
            enhanced.append(
                {
                    "quantity": purchase.get("quantity"),
                    "purchase_date": purchase.get("purchasing_date"),
                    "delivery_date": purchase.get("delivered_date"),
                    "total_price": purchase.get("total_price"),
                    "product": product_info,
                }
            )
        return enhanced


def database_agent(customer_id: str) -> Dict[str, Any]:
    """Return the database agent configuration bound to a customer."""
    agent = DatabaseAgent(customer_id)
    return {
        "id": "Assistant_Database_Agent",
        "name": "Database Agent",
        "description": (
            "Interacts with Customer, Product and Purchases containers in "
            "Cosmos DB."
        ),
        "system_message": (
            "You are a database assistant that manages records in Cosmos DB.\n"
            "Use the provided tools carefully and confirm details with the "
            "user before mutating data."
        ),
        "tools": [
            {
                "name": "create_purchases_record",
                "description": "Create a new purchase record.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "purchase_record": {
                            "type": "object",
                            "description": (
                                "Payload containing product details and "
                                "quantity."
                            ),
                        }
                    },
                    "required": ["purchase_record"],
                },
                "returns": agent.create_purchases_record,
            },
            {
                "name": "update_customer_record",
                "description": "Update customer profile information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "address": {"type": "object"},
                        "phone_number": {"type": "string"},
                    },
                },
                "returns": agent.update_customer_record,
            },
            {
                "name": "get_customer_record",
                "description": "Retrieve the current customer's profile.",
                "parameters": {"type": "object", "properties": {}},
                "returns": agent.get_customer_record,
            },
            {
                "name": "get_product_record",
                "description": "Retrieve product catalog details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "Specific product identifier.",
                        }
                    },
                },
                "returns": agent.get_product_record,
            },
            {
                "name": "get_purchases_record",
                "description": "Retrieve purchase history for the customer.",
                "parameters": {"type": "object", "properties": {}},
                "returns": agent.get_purchases_record,
            },
        ],
    }
