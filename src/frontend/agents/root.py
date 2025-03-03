import os
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
import util
import json
import logging
import re

util.load_dotenv_from_azd()

# Bing Search Configuration
bing_api_key = os.getenv("BING_SEARCH_API_KEY")
has_bing_api_key = bing_api_key is not None and bing_api_key != ''

# CosmosDB Configuration
credential = DefaultAzureCredential()
cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
cosmos_client = CosmosClient(cosmos_endpoint, credential)
database_name = os.getenv("COSMOSDB_DATABASE")
database = cosmos_client.create_database_if_not_exists(id=database_name)
machine_container_name = "Machine"
operations_container_name = "Operations"
operator_container_name = "Operator"

def get_operator_info(operator_id):
    # Get the database and container
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(operator_container_name)
    try:
        # Query the container for the operator information
        query = f"""SELECT c.OperatorID, c.OperatorName, c.Shift, c.Role 
                    FROM c 
                    WHERE c.OperatorID = {operator_id}"""
        items = list(container.query_items(query, enable_cross_partition_query=True))
        
        if items:
            return items[0]
        else:
            return None
    except exceptions.CosmosResourceNotFoundError as e:
        logging.error(f"CosmosHttpResponseError: {e}")
        return None

def root_assistant(machine_id=None, operator_id=None):
    """
    Return the Root Agent Configuration
    
    Args:
        machine_id: Optional machine ID for context
        operator_id: Optional operator ID for context
    """
    
    # Define operator context for prompt

    operator_info = get_operator_info(operator_id)
    operator_context = f"Operator_Name: {operator_info['OperatorName']} (Operator_ID: {operator_id}, Role: {operator_info['Role']}, Shift: {operator_info['Shift']})."
    
    return {
        "id": "AssistantRoot",
        "name": "Greeter",
        "description": """Call this if:   
        - You need to greet the User by first name.
        - You need to check if User has any additional questions.
        - You need to close the conversation after the User's request has been resolved.
        DO NOT CALL THIS IF:  
        - You need to fetch information from the internal knowledge base which is literally asked by the user -> use Assistant_internal_kb_agent
        - You need to send an email to the specified user -> use Assistant_Executive_Assistant
        - You need to manage database records (get/create/update any of the Operator, Machine and Operations container/table) -> use Assistant_Database_Agent 
        - You need to search the web for current information -> use Assistant_WebSearch
        """,
        "system_message": f"""You are an AI assistant working for the company Lindt, that helps an operator with machinery field operations.
        You have 4 other agents to help you with specific tasks on searching the web for up-to-date information retrieval, sending emails, perform database interactions and retrieve information from internal knowledge base.
        Keep sentences short and simple, suitable for a voice conversation, so it's *super* important that answers are as short as possible. Use professional language.
        Your task are:
        - Greet the User at first and ask how you can help.
        - ALWAYS route the proper agent to handle ALL specific requests via function call. NEVER provide answers yourself.
        - Check if the User has any additional questions. If not, close the conversation.
        - Close the conversation after the User's request has been resolved. Thank the Customer for their time and wish them a good day.

        IMPORTANT NOTES:
        - Make sure to act politely and professionally.  
        - NEVER pretend to act on behalf of the company. NEVER provide false information.
        {"- Inform users that web search functionality requires a Bing Search API key if they ask about web search and it's not available." if not has_bing_api_key else ""}
        IMPORTANT: Use only existing functions to handle requests. Do not invent new function names.
        Here is the information about the current user that is logged in as operator: {operator_context}
        """,
        "tools": []
    }