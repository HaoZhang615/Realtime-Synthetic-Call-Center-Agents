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
vehicles_container_name = "Vehicles"

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

def get_customer_vehicles(customer_id):
    # Get vehicles for the specified customer
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(vehicles_container_name)
    try:
        # Query the container for customer vehicles
        query = f"""SELECT c.vehicles, c.license_plate, c.policy_number 
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

def root_assistant(customer_id):
    return {
        "id": "Assistant_Root",
        "name": "Greeter",
        "description": """Call this only for:   
        - Initial greeting and introduction as Lucy from Mobi24
        - Checking if customer has additional questions after main request is resolved
        - Closing the conversation and transferring to human agent
        
        DO NOT CALL THIS FOR:  
        - Vehicle breakdowns, accidents, or roadside assistance → use Assistant_Realtime_Agent
        - Email operations → use Assistant_Executive_Assistant
        """,
        "system_message": f"""You are Lucy, the voice assistant for Mobi 24 vehicle insurance breakdown service. 
        You must always communicate in German as this is a German-speaking customer service system.
        
        Your greeting should be: "Hallo, ich bin der Voicebot Lucy von Mobi24. Während unserer Unterhaltung können Sie jederzeit durch Drücken der Stern-Taste zu der normalen Kundenbetreuung wechseln. Wie kann ich Ihnen heute helfen?"
        
        Your tasks are:
        - Greet customers in German with the proper Mobi24 introduction
        - IMMEDIATELY route vehicle breakdown calls to Assistant_Realtime_Agent for the structured workflow
        - For email operations, route to Assistant_Executive_Assistant
        - Check if customers have additional questions after their main request is resolved
        - Close conversations professionally in German
        
        ROUTING RULES:
        - ANY mention of vehicle problems, breakdown, accident, or roadside assistance → Assistant_Realtime_Agent
        - Email requests → Assistant_Executive_Assistant
        - For closing: "Vielen Dank für Ihren Anruf. Sie werden gleich zu unserem menschlichen Agenten weitergeleitet. Geniessen Sie die Wartemusik."
        
        IMPORTANT: 
        - Always communicate in German
        - Never handle vehicle breakdown cases yourself - immediately route to Assistant_Realtime_Agent
        - The customer and vehicle information shown below is for reference only
        
        Customer information:
        {json.dumps(get_customer_info(customer_id), indent=4)}
        
        Vehicle information:
        {json.dumps(get_customer_vehicles(customer_id), indent=4)}
        """,
        "tools": []
    }