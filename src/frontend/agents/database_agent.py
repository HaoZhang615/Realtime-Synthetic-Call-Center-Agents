import os
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
import util
from typing import Dict, List, Optional, Union
import logging

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

def validate_customer_exists(container, customer_id: str) -> bool:
    """Validates if a customer exists in the database."""
    query = f"SELECT VALUE COUNT(1) FROM c WHERE c.customer_id = '{customer_id}'"
    result = list(container.query_items(query, enable_cross_partition_query=True))
    return result[0] > 0 if result else False

def create_purchases_record(customer_id: str, purchase_record: Dict) -> str:
    """Creates a new purchase record in the Purchases container.
    
    Args:
        customer_id: The ID of the customer making the purchase
        purchase_record: Dict containing:
            - product_id: str
            - quantity: int
            - purchasing_date: str (ISO format)
            - total_price: float
    """
    container = database.get_container_client(purchase_container_name)
    
    # Validate customer exists
    customer_container = database.get_container_client(customer_container_name)
    if not validate_customer_exists(customer_container, customer_id):
        return f"Customer with ID {customer_id} not found"
    
    # Ensure required fields
    purchase_record["customer_id"] = customer_id
    if "product_id" not in purchase_record:
        return "Missing required field: product_id"
    
    try:
        container.create_item(body=purchase_record)
        return "Purchase record created successfully."
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Failed to create purchase record: {e}")
        return f"Failed to create purchase record: {str(e)}"

def update_customer_record(customer_id: str, customer_record: Dict) -> str:
    """Updates an existing customer record in the Customer container.
    
    Args:
        customer_id: The ID of the customer to update
        customer_record: Dict containing any of:
            - first_name: str
            - last_name: str
            - email: str
            - address: Dict[street, city, postal_code, country]
            - phone_number: str
    """
    container = database.get_container_client(customer_container_name)
    
    # Validate customer exists
    if not validate_customer_exists(container, customer_id):
        return f"Customer with ID {customer_id} not found"
    
    try:
        # Get existing record
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        existing_record = list(container.query_items(query, enable_cross_partition_query=True))[0]
        
        # Update only provided fields
        for key, value in customer_record.items():
            existing_record[key] = value
        
        container.upsert_item(body=existing_record)
        return "Customer record updated successfully."
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Failed to update customer record: {e}")
        return f"Failed to update customer record: {str(e)}"

def get_customer_record(customer_id: str) -> Union[Dict, str]:
    """Retrieves a customer record from the Customer container.
    
    Args:
        customer_id: The ID of the customer to retrieve
    
    Returns:
        Dict containing customer information or error message
    """
    container = database.get_container_client(customer_container_name)
    try:
        query = f"""SELECT 
            c.customer_id,
            c.first_name,
            c.last_name,
            c.email,
            c.address,
            c.phone_number
        FROM c 
        WHERE c.customer_id = '{customer_id}'"""
        
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        if not items:
            return f"No customer found with ID: {customer_id}"
        return items[0]
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Failed to get customer record: {e}")
        return f"Failed to get customer record: {str(e)}"

def get_product_record(product_id: Optional[str] = None) -> Union[List[Dict], Dict, str]:
    """Retrieves product records from the Product container.
    
    Args:
        product_id: Optional; specific product ID to retrieve
    
    Returns:
        List of all products or specific product details
    """
    container = database.get_container_client(product_container_name)
    try:
        if (product_id):
            query = f"""SELECT 
                c.product_id,
                c.name,
                c.category,
                c.type,
                c.brand,
                c.company,
                c.unit_price,
                c.weight
            FROM c 
            WHERE c.product_id = '{product_id}'"""
            items = list(container.query_items(query=query, enable_cross_partition_query=True))
            return items[0] if items else f"No product found with ID: {product_id}"
        else:
            items = list(container.read_all_items())
            return items if items else "No products found."
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Failed to get product record(s): {e}")
        return f"Failed to get product record(s): {str(e)}"

def get_purchases_record(customer_id: str) -> Union[List[Dict], str]:
    """Retrieves all purchase records for a specific customer.
    
    Args:
        customer_id: The ID of the customer to retrieve purchases for
    
    Returns:
        List of purchase records or error message
    """
    container = database.get_container_client(purchase_container_name)
    
    # Validate customer exists
    customer_container = database.get_container_client(customer_container_name)
    if not validate_customer_exists(customer_container, customer_id):
        return f"Customer with ID {customer_id} not found"
    
    try:
        query = f"""SELECT 
            c.customer_id,
            c.product_id,
            c.quantity,
            c.purchasing_date,
            c.delivered_date,
            c.order_number,
            c.total_price
        FROM c 
        WHERE c.customer_id = '{customer_id}'"""
        
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return items if items else f"No purchases found for customer: {customer_id}"
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Failed to get purchase records: {e}")
        return f"Failed to get purchase records: {str(e)}"

# Agent Definition
database_agent = {
    "id": "Assistant_Database_Agent",
    "name": "Database Agent",
    "description": """This agent interacts with a database that contains 'Customer', 'Product' and 'Purchases' containers/tables. It provides specific tools for creating purchases, updating customer information, and retrieving records from all containers.""",
    "system_message": """
You are a database assistant that manages records in CosmosDB with specific operations for each container type. Use the provided tools to perform database operations.
Interaction goes over voice, so it's *super* important that answers are as short as possible. Use professional language.

Available operations:
- create_purchases_record (requires customer_id): this action creates a new purchase record in the Purchases container.
- update_customer_record (requires customer_id): this action updates an existing customer record in the Customer container.
- get_customer_record (requires customer_id): this action retrieves a customer's information from the Customer container.
- get_product_record (optional product_id): this action retrieves all available products or a specific product from the Product container.
- get_purchases_record (requires customer_id): this action retrieves all purchases for a specific customer from the Purchases container.

NOTES:
- Before updating any records, make sure to confirm the details with the user.
- All operations that modify or retrieve customer data require a valid customer_id.
- Purchases are always associated with both a customer_id and product_id.
- Before creating or updating a record, use the 'get' tools to retrieve the required schema of the respective container and then infer the new record to use in the 'create' or 'update' tool calls. E.g. if you need to update a customer record, first call get_customer_record to get the schema of the customer record and then use that schema to infer the new record to use in the update_customer_record tool call.

IMPORTANT: Never invent new tool or function names. Always use only 'create_purchases_record', 'update_customer_record', 'get_customer_record', 'get_product_record', or 'get_purchases_record' when interacting with the database.
""",
    "tools": [
        {
            "name": "create_purchases_record",
            "description": "Create a new purchase record in the Purchases container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The ID of the customer making the purchase"
                    },
                    "purchase_record": {
                        "type": "object",
                        "description": "The purchase record containing product_id, quantity, purchasing_date, and total_price"
                    }
                },
                "required": ["customer_id", "purchase_record"]
            },
            "returns": create_purchases_record
        },
        {
            "name": "update_customer_record",
            "description": "Update customer information in the Customer container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The ID of the customer to update"
                    },
                    "customer_record": {
                        "type": "object",
                        "description": "The customer record fields to update"
                    }
                },
                "required": ["customer_id", "customer_record"]
            },
            "returns": update_customer_record
        },
        {
            "name": "get_customer_record",
            "description": "Retrieve a customer's information using their customer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID to look up"
                    }
                },
                "required": ["customer_id"]
            },
            "returns": get_customer_record
        },
        {
            "name": "get_product_record",
            "description": "Retrieve all products or a specific product from the catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Optional: The specific product ID to look up"
                    }
                },
                "required": []
            },
            "returns": get_product_record
        },
        {
            "name": "get_purchases_record",
            "description": "Retrieve all purchases for a specific customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID to look up purchases for"
                    }
                },
                "required": ["customer_id"]
            },
            "returns": get_purchases_record
        }
    ]
}
