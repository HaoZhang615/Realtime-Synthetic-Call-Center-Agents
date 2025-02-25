import os
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
import util
import json
import logging

util.load_dotenv_from_azd()
# CosmosDB Configuration
credential = DefaultAzureCredential()
cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
cosmos_client = CosmosClient(cosmos_endpoint, credential)
database_name = os.getenv("COSMOSDB_DATABASE")
database = cosmos_client.create_database_if_not_exists(id=database_name)
customer_container_name = "Customer"
product_container_name = "Product"

def get_customer_info(customer_id):
    # Get the database and container
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(customer_container_name)
    try:
        # Query the container for the customer information
        query = f"""SELECT c.customer_id , c.first_name, c.last_name, c.email, c.address.city, c.address.postal_code, c.address.country, c.phone_number 
                    FROM c 
                    WHERE c.customer_id = '{customer_id}'"""
        items = list(container.query_items(query, enable_cross_partition_query=True))
        
        if items:
            return items[0]
        else:
            return None
    except exceptions.CosmosResourceNotFoundError as e:
        logging.error(f"CosmosHttpResponseError: {e}")
        return None

def get_target_company():
    # use the first item in the Product container and get the value of the field "company"
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(product_container_name)
    try:
        # Query the container for the first item
        items = list(container.read_all_items())
        if items:
            return items[0]["company"]
        else:
            return None
    except exceptions.CosmosResourceNotFoundError as e:
        logging.error(f"CosmosHttpResponseError: {e}")
        return None

def root_assistant(customer_id):
    return {
        "id": "Assistant_Root",
        "name": "Greeter",
        "description": """Call this if:   
        - You need to greet the User.
        - You need to check if User has any additional questions.
        - You need to close the conversation after the User's request has been resolved.
        DO NOT CALL THIS IF:  
        - You need to fetch information from the internal knowledge base which is literally asked by the user -> use Assistant_internal_kb_agent
        - You need to send an email to the specified user -> use Assistant_Executive_Assistant
        - You need to manage database records (get/create/update any of the Customer, Product and Purchases container/table) -> use Assistant_Database_Agent 
        - You need to search the web for current information -> use Assistant_WebSearch
        """,
        "system_message": f"""You are a helpful assistant working for the company {get_target_company()}. 
        You have 4 other agents to help you with specific tasks on searching the web for up-to-date information retrieval, sending emails, updating experiment results, and retrieve information from internal knowledge base.
        If user is asking about any related products or services from {get_target_company()}'s competitors or from the same industry, you promote {get_target_company()}'s equivalent products by directing to the Assistant_WebSearch to search the same category across {get_target_company()}'s portfolio.
        Keep sentences short and simple, suitable for a voice conversation, so it's *super* important that answers are as short as possible. Use professional language.
        
        Your task are:
        - Greet the User at first and ask how you can help.
        - ALWAYS route the proper agent to handle ALL specific requests via function call. NEVER provide answers yourself.
        - Check if the User has any additional questions. If not, close the conversation.
        - Close the conversation after the User's request has been resolved. Thank the Customer for their time and wish them a good day.
        
        IMPORTANT NOTES:
        - Make sure to act politely and professionally.  
        - NEVER pretend to act on behalf of the company. NEVER provide false information.
        IMPORTANT: Use only existing functions to handle requests. Do not invent new function names like 'RetrieveProducts'.
        Here are the information of the customer you are talking to:
        {json.dumps(get_customer_info(customer_id), indent=4)}
        """,
        "tools": []
    }