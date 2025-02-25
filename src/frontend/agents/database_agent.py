import os
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
import util
from typing import Dict, List, Optional, Union
import logging
import uuid
from datetime import datetime  # Add datetime import

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

class DatabaseAgent:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id

    def validate_customer_exists(self, container) -> bool:
        """Validates if a customer exists in the database."""
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.customer_id = @customer_id"
        parameters = [{"name": "@customer_id", "value": self.customer_id}]
        result = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return result[0] > 0 if result else False

    def create_purchases_record(self, parameters: Dict) -> str:
        """Creates a new purchase record in the Purchases container."""
        purchase_record = parameters.get('purchase_record', {})
        
        # Check if product_id is missing in purchase_record
        if "product_id" not in purchase_record:
            # First, check if top-level product_id is provided
            if "product_id" in parameters:
                purchase_record["product_id"] = parameters["product_id"]
            # Otherwise, if a product_name is provided in purchase_record, derive product_id from it
            elif "product_name" in purchase_record:
                product_name = purchase_record["product_name"]
                product_container = database.get_container_client(product_container_name)
                query = "SELECT TOP 1 * FROM c WHERE CONTAINS(c.name, @name)"
                query_params = [{"name": "@name", "value": product_name}]
                results = list(product_container.query_items(query=query, parameters=query_params, enable_cross_partition_query=True))
                if results:
                    purchase_record["product_id"] = results[0]["product_id"]
                    # Optionally remove product_name to avoid redundancy
                    del purchase_record["product_name"]
                else:
                    return f"Product with name '{product_name}' not found. Please check the product name."

        container = database.get_container_client(purchase_container_name)
        product_container = database.get_container_client(product_container_name)
        
        # Validate customer exists
        customer_container = database.get_container_client(customer_container_name)
        if not self.validate_customer_exists(customer_container):
            return f"Customer with ID {self.customer_id} not found"
        
        # Get product details
        if "product_id" in purchase_record:
            product_query = "SELECT * FROM c WHERE c.product_id = @product_id"
            product_params = [{"name": "@product_id", "value": purchase_record["product_id"]}]
            product_results = list(product_container.query_items(
                query=product_query,
                parameters=product_params,
                enable_cross_partition_query=True
            ))
            if product_results:
                product_details = product_results[0]
            else:
                return f"Product with ID {purchase_record['product_id']} not found"
        else:
            return "Missing required field: product_id"

        # Create final purchase record with required schema
        final_record = {
            "customer_id": self.customer_id,
            "product_id": purchase_record["product_id"],
            "quantity": purchase_record.get("quantity", 1),  # Default to 1 if not specified
            "purchasing_date": datetime.utcnow().isoformat(),
            "order_number": str(uuid.uuid4().hex),
            "product_details": product_details,
            "total_price": product_details.get("unit_price", 0) * purchase_record.get("quantity", 1),
            "id": str(uuid.uuid4())
        }
        
        try:
            container.create_item(body=final_record)
            return "Purchase record created successfully."
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to create purchase record: {e}")
            return f"Failed to create purchase record: {str(e)}"

    def update_customer_record(self, parameters: Dict) -> str:
        """Updates an existing customer record in the Customer container."""
        container = database.get_container_client(customer_container_name)

        # Query to find the customer document using customer_id
        query = f"SELECT * FROM c WHERE c.customer_id = '{self.customer_id}'"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        if not items:
            raise Exception("Customer record not found")
        
        customer_doc = items[0]
        
        # Extract only updatable fields from parameters
        updatable_fields = ['first_name', 'last_name', 'email', 'address', 'phone_number']
        update_data = {k: v for k, v in parameters.items() if k in updatable_fields}
        
        # Update the document with allowed fields only
        customer_doc.update(update_data)
        
        # Replace the item without explicitly passing the partition key
        container.replace_item(
            item=customer_doc,
            body=customer_doc
        )
        
        return {"status": "success", "message": "Customer record updated successfully"}

    def get_customer_record(self, parameters: Dict) -> Union[Dict, str]:
        """Retrieves the customer record from the Customer container."""
        container = database.get_container_client(customer_container_name)
        try:
            query = """SELECT 
                c.customer_id,
                c.first_name,
                c.last_name,
                c.email,
                c.address,
                c.phone_number
            FROM c 
            WHERE c.customer_id = @customer_id"""
            
            parameters = [{"name": "@customer_id", "value": self.customer_id}]
            items = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            if not items:
                return f"No customer found with ID: {self.customer_id}"
            return items[0]
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get customer record: {e}")
            return f"Failed to get customer record: {str(e)}"

    def get_product_record(self, parameters: Dict) -> Union[List[Dict], Dict, str]:
        """Retrieves product records from the Product container."""
        container = database.get_container_client(product_container_name)
        try:
            if ("product_id" in parameters):
                query = """SELECT 
                    c.product_id,
                    c.name,
                    c.category,
                    c.type,
                    c.brand,
                    c.company,
                    c.unit_price,
                    c.weight
                FROM c 
                WHERE c.product_id = @product_id"""
                query_parameters = [{"name": "@product_id", "value": parameters["product_id"]}]
                items = list(container.query_items(query=query, parameters=query_parameters, enable_cross_partition_query=True))
                return items[0] if items else f"No product found with ID: {parameters['product_id']}"
            else:
                items = list(container.read_all_items())
                return items if items else "No products found."
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get product record(s): {e}")
            return f"Failed to get product record(s): {str(e)}"

    def get_purchases_record(self, parameters: Dict) -> Union[List[Dict], str]:
        """Retrieves all purchase records for the current customer with product details."""
        purchases_container = database.get_container_client(purchase_container_name)
        product_container = database.get_container_client(product_container_name)
        
        # Validate customer exists
        customer_container = database.get_container_client(customer_container_name)
        if not self.validate_customer_exists(customer_container):
            return f"Customer with ID {self.customer_id} not found"
        
        try:
            # First get all purchases for the customer
            query = """SELECT 
                c.customer_id,
                c.product_id,
                c.quantity,
                c.purchasing_date,
                c.delivered_date,
                c.order_number,
                c.total_price
            FROM c 
            WHERE c.customer_id = @customer_id"""
            
            parameters = [{"name": "@customer_id", "value": self.customer_id}]
            purchases = list(purchases_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            if not purchases:
                return f"No purchases found for customer: {self.customer_id}"

            # Enhance purchase records with product details
            enhanced_purchases = []
            for purchase in purchases:
                # Get product details
                product_query = """SELECT 
                    c.name,
                    c.category,
                    c.type,
                    c.brand,
                    c.company,
                    c.unit_price,
                    c.weight
                FROM c 
                WHERE c.product_id = @product_id"""
                product_params = [{"name": "@product_id", "value": purchase["product_id"]}]
                
                product = list(product_container.query_items(
                    query=product_query,
                    parameters=product_params,
                    enable_cross_partition_query=True
                ))

                if product:
                    # Create clean purchase record without technical fields
                    clean_purchase = {
                        "quantity": purchase["quantity"],
                        "purchase_date": purchase["purchasing_date"],
                        "delivery_date": purchase["delivered_date"],
                        "total_price": purchase["total_price"],
                        "product": {
                            "name": product[0]["name"],
                            "category": product[0]["category"],
                            "type": product[0]["type"],
                            "brand": product[0]["brand"],
                            "company": product[0]["company"],
                            "price": product[0]["unit_price"],
                            "weight": product[0]["weight"]
                        }
                    }
                    enhanced_purchases.append(clean_purchase)
                else:
                    # Include purchase with minimal technical details if product not found
                    clean_purchase = {
                        "quantity": purchase["quantity"],
                        "purchase_date": purchase["purchasing_date"],
                        "delivery_date": purchase["delivered_date"],
                        "total_price": purchase["total_price"],
                        "product": {"error": "Product details not found"}
                    }
                    enhanced_purchases.append(clean_purchase)

            return enhanced_purchases

        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get purchase records: {e}")
            return f"Failed to get purchase records: {str(e)}"

def database_agent(customer_id: str):
    """Creates and returns the database agent configuration with the given customer_id."""
    agent = DatabaseAgent(customer_id)
    
    return {
        "id": "Assistant_Database_Agent",
        "name": "Database Agent",
        "description": """This agent interacts with a database that contains 'Customer', 'Product' and 'Purchases' containers/tables. It provides specific tools for creating purchases, updating customer information, and retrieving records from all containers.""",
        "system_message": """
You are a database assistant that manages records in CosmosDB with specific operations for each container type. Use the provided tools to perform database operations.
Interaction goes over voice, so it's *super* important that answers are as short as possible. Use professional language.

Available operations:
- create_purchases_record: creates a new purchase record in the Purchases container.
- update_customer_record: updates the existing customer record in the Customer container.
- get_customer_record: retrieves the customer's information from the Customer container.
- get_product_record: retrieves all available products or a specific product from the Product container.
- get_purchases_record: retrieves all purchases for the current customer from the Purchases container.

NOTES:
- Before updating any records, make sure to confirm the details with the user.
- All operations automatically use the current customer's ID.
- Purchases are always associated with both the current customer and a product_id.
- Before creating or updating a record, use the 'get' tools to retrieve the required schema of the respective container.

IMPORTANT: Never invent new tool or function names. Always use only the provided tools when interacting with the database.
""",
        "tools": [
            {
                "name": "create_purchases_record",
                "description": "Create a new purchase record in the Purchases container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "purchase_record": {
                            "type": "object",
                            "description": "The purchase record containing product_id and quantity."
                        }
                    },
                    "required": ["purchase_record"]
                },
                "returns": agent.create_purchases_record
            },
            {
                "name": "update_customer_record",
                "description": "Update customer information in the Customer container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string", "description": "Customer's first name"},
                        "last_name": {"type": "string", "description": "Customer's last name"},
                        "email": {"type": "string", "description": "Customer's email address"},
                        "address": {
                            "type": "object",
                            "properties": {
                                "street": {"type": "string"},
                                "city": {"type": "string"},
                                "postal_code": {"type": "string"},
                                "country": {"type": "string"}
                            }
                        },
                        "phone_number": {"type": "string", "description": "Customer's phone number"}
                    }
                },
                "returns": agent.update_customer_record
            },
            {
                "name": "get_customer_record",
                "description": "Retrieve the current customer's information.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "returns": agent.get_customer_record
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
                "returns": agent.get_product_record
            },
            {
                "name": "get_purchases_record",
                "description": "Retrieve all purchases for the current customer.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "returns": agent.get_purchases_record
            }
        ]
    }
