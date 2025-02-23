# Refactored file to use Cosmos SDK for direct database interactions
import os
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
import util
util.load_dotenv_from_azd()

# CosmosDB Configuration
credential = DefaultAzureCredential()
cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
cosmos_client = CosmosClient(cosmos_endpoint, credential)
database_name = os.getenv("COSMOSDB_DATABASE")
database = cosmos_client.create_database_if_not_exists(id=database_name)
customer_container_name = "Customer"
purchase_container_name = "Purchases"
product_container_name = "Product"


def create_record(params):
    """Creates a new record in the specified CosmosDB container using the SDK."""
    container_name = params.get("container")
    record = params.get("record")
    if container_name not in ["Customer", "Purchases"]:
        return f"Unsupported container: {container_name}. Only 'Customer' and 'Purchases' are supported."
    container = database.get_container_client(container_name)
    try:
        container.create_item(body=record)
        return "Record created successfully."
    except exceptions.CosmosHttpResponseError as e:
        return f"Failed to create record: {e}"


def update_record(params):
    """Updates an existing record in the specified CosmosDB container using the SDK. Uses upsert to update or insert."""
    container_name = params.get("container")
    record = params.get("record")
    if container_name not in ["Customer", "Purchases"]:
        return f"Unsupported container: {container_name}. Only 'Customer' and 'Purchases' are supported."
    container = database.get_container_client(container_name)
    try:
        container.upsert_item(body=record)
        return "Record updated successfully."
    except exceptions.CosmosHttpResponseError as e:
        return f"Failed to update record: {e}"


def get_record(params):
    """Retrieves records from the specified CosmosDB container using customer_id as key.
    For the 'Customer' container, returns the customer's information.
    For the 'Purchases' container, returns all purchase records for the customer.
    Requires 'customer_id' to be provided.
    """
    container_name = params.get("container")
    if container_name not in ["Customer", "Purchases", "Product"]:
        return f"Unsupported container: {container_name}. Only 'Customer', 'Purchases' and 'Product' are supported."
    
    container = database.get_container_client(container_name)
    
    if container_name == "Product":
        try:
            items = list(container.read_all_items())
            return items if items else "No products found."
        except exceptions.CosmosHttpResponseError as e:
            return f"Failed to get records: {e}"
    
    customer_id = params.get("customer_id")
    if not customer_id:
        return "customer_id is required for Customer and Purchases containers."
    
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        if container_name == "Customer":
            return items[0] if items else f"No customer information found for customer_id: {customer_id}"
        else:  # Purchases
            return items if items else f"No purchases found for customer_id: {customer_id}"
    except exceptions.CosmosHttpResponseError as e:
        return f"Failed to get record(s): {e}"


# Agent Definition

database_agent = {
    "id": "Database_Agent",
    "name": "Database Agent",
    "description": """This agent interacts with a database that contains 'Customer','Product' and 'Purchases' containers/tables. It provides tools to create and update in the 'Customer' and 'Purchases' containers, as well as retrieve records in all containers/tables. The customer_id is used as the key for record retrieval, create and update.""",
    "system_message": """
You are a database assistant that manages records in CosmosDB by creating, updating, and retrieving records. Use the provided tools to perform database operations.
Interaction goes over voice, so it's *super* important that answers are as short as possible. Use professional language.
Your tasks are:
- Create a new record in the specified container using the "create_record" tool.
- Update an existing record in the specified container using the "update_record" tool.
- Retrieve records from the specified container using the "get_record" tool.

NOTES:
- Before updating any records, make sure to confirm the details with the user.
""",
    "tools": [
        {
            "name": "create_record",
            "description": "Create a new record in a specified CosmosDB container. Provide the container name and record as a JSON object.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "The target container name.",
                        "enum": ["Customer", "Purchases"]
                    },
                    "record": {
                        "type": "object",
                        "description": "The record to create in the container with the customer_id as key."
                    }
                },
                "required": ["container", "record"]
            },
            "returns": create_record
        },
        {
            "name": "update_record",
            "description": "Update an existing record in a specified CosmosDB container. Provide the container name and record (including its technical id and customer_id as the partition key) as a JSON object.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "The target container name.",
                        "enum": ["Customer", "Purchases"]
                    },
                    "record": {
                        "type": "object",
                        "description": "The updated record with the customer_id as key."
                    }
                },
                "required": ["container", "record"]
            },
            "returns": update_record
        },
        {
            "name": "get_record",
            "description": "Retrieve records from a specified CosmosDB container using customer_id as key. If no 'customer_id' are provided and the to be queried container is 'Product', returns all records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "The target container name.",
                        "enum": ["Customer", "Purchases", "Product"]
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "The customer id used as the partition key for retrieval (optional)."
                    }
                },
                "required": ["container"]
            },
            "returns": get_record
        }
    ]
}
