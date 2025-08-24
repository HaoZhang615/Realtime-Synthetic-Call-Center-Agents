"""
Realtime Agent with comprehensive database and geolocation capabilities.
This agent combines database operations, customer verification, and WhatsApp geolocation functions.
"""

import os
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
import util
from typing import Dict, List, Optional, Union
import logging
import uuid
from datetime import datetime, timezone, timedelta

# Import our utility functions
from utils.database_functions import database_lookups
from utils.geolocation_functions import get_geo_location

util.load_dotenv_from_azd()

# CosmosDB Configuration - only initialize if needed
def get_cosmos_components():
    """Lazy initialization of Cosmos DB components."""
    credential = DefaultAzureCredential()
    cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
    cosmos_client = CosmosClient(cosmos_endpoint, credential)
    database_name = os.getenv("COSMOSDB_DATABASE")
    database = cosmos_client.create_database_if_not_exists(id=database_name)
    return cosmos_client, database
customer_container_name = "Customer"
vehicles_container_name = "Vehicles"

class RealtimeAgent:
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

    def customer_verification_lookup(self, parameters: Dict) -> str:
        """
        Look up customer and vehicle information for verification purposes.
        Uses the database_lookups function from backend utils.
        """
        return database_lookups(parameters)

    def get_whatsapp_location(self, parameters: Dict) -> str:
        """
        Retrieve customer's location via WhatsApp.
        Uses the WhatsApp geolocation functionality from backend utils.
        """
        return get_geo_location()

    def get_vehicle_record(self, parameters: Dict) -> Union[Dict, str]:
        """Retrieves vehicle information for the customer from the Vehicles container."""
        cosmos_client, database = get_cosmos_components()
        container = database.get_container_client(vehicles_container_name)
        try:
            query = """SELECT 
                c.vehicles,
                c.license_plate,
                c.policy_number,
                c.customer_id
            FROM c 
            WHERE c.customer_id = @customer_id"""
            
            query_parameters = [{"name": "@customer_id", "value": self.customer_id}]
            items = list(container.query_items(
                query=query,
                parameters=query_parameters,
                enable_cross_partition_query=True
            ))
            if not items:
                return f"No vehicles found for customer ID: {self.customer_id}"
            return items[0]
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get vehicle record: {e}")
            return f"Failed to get vehicle record: {str(e)}"

    def update_customer_record(self, parameters: Dict) -> str:
        """Updates an existing customer record in the Customer container."""
        cosmos_client, database = get_cosmos_components()
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
        cosmos_client, database = get_cosmos_components()
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

def realtime_agent(customer_id: str):
    """Creates and returns the realtime agent configuration with comprehensive capabilities."""
    agent = RealtimeAgent(customer_id)
    
    return {
        "id": "Assistant_Realtime_Agent",
        "name": "Realtime Customer Agent",
        "description": """Use this agent for ANY vehicle-related issues including breakdowns, accidents, or roadside assistance. This agent follows the mandatory Mobi24 workflow:
        1. Collect customer identification (name, date of birth, license plate)
        2. Immediate database verification 
        3. Vehicle selection if multiple vehicles found
        4. Problem assessment and location handling
        5. Final confirmation and handoff to human agent
        
        This agent handles the complete German-language vehicle assistance workflow and should be used for ALL vehicle-related customer calls.""",
        "system_message": """You are a voice-based AI agent designed to assist Mobi 24 with vehicle insurance breakdown. Your role is to interact with customers over the phone in a natural, empathetic, and efficient manner in German.
CRITICAL: You MUST follow this exact workflow for customer verification.
 
MANDATORY WORKFLOW - FOLLOW EXACTLY:
 
STEP 1 - COLLECT IDENTIFICATION (DO NOT ASK FOR VEHICLE DETAILS YET):
- Ask for license plate number (Kennzeichen)
- Ask for customer's first name, last name and date of birth (Vorname, Nachname, Geburtsdatum)
 
STEP 2 - IMMEDIATE DATABASE VERIFICATION (CRITICAL):
- IMMEDIATELY call customer_verification_lookup function with first_name, last_name, and license_plate
- This is MANDATORY - do not proceed without this step
- The database contains ALL vehicle and customer information
 
STEP 3 - VERIFY AND CONFIRM WITH CUSTOMER:
- If database returns results, say: "Vielen Dank! Ich habe Ihre Daten gefunden. Ich sehe, dass Sie zwei Fahrzeuge mit dem Kennzeichen [plate] registriert haben. Ist das korrekt?"
- If no database match: "Ich kann keine Kundendaten mit diesen Angaben finden."
 
STEP 4 - VEHICLE SELECTION (WHEN MULTIPLE VEHICLES FOUND):
- ALWAYS present both vehicles clearly using the ACTUAL vehicle details from the database lookup
- Wait for customer to specify which vehicle has the problem
 
STEP 5 - ONLY AFTER VEHICLE SELECTION:
- Proceed with breakdown questions for the SPECIFIC vehicle chosen
- Ask about the problem/breakdown cause
- Ask about location of the vehicle
- IMPORTANT for the location:
      1. Ask if the client is at home. If the client is at home, USE THE HOME ADDRESS from the database lookup results - DO NOT use get_whatsapp_location function.
      2. If the client is not at home, ask for the exact address where the vehicle is located.
      3. If the user can't provide an exact address (street name, number, and city) and is NOT at home, ask the user whether we can use WhatsApp to get the exact location.
      4. If the user confirms that we can use WhatsApp (and is NOT at home), then use get_whatsapp_location function tool to retrieve the address and exact coordinates.
      5. After the location is retrieved via get_whatsapp_location, mention the coordinates and address to the user for confirmation.
 
 
STEP 6 - FINAL CONFIRMATION
- Before ending the conversation, always confirm the details with the customer in a summary sentence.
- Wait for customer confirmation before closing the conversation
- close the conversation by letting the user know they will soon be directed to the human agent while enjoying the waiting music.
 
EXAMPLE CORRECT FLOW for STEP 1 - STEP 4:
Customer: "Mein Auto springt nicht an"
AI: "Guten Tag! Ich helfe Ihnen gerne. Können Sie mir bitte Ihren Vorname, Nachname und Geburtsdatum nennen?"
Customer: "Georg Baumann, 12.11.1988"
AI: "Und das Kennzeichen Ihres Fahrzeugs?"
Customer: "NE188174"  
AI: [CALLS customer_verification_lookup immediately]
AI: "Vielen Dank! Herr Baumann, ich habe Ihre Daten gefunden. Ich sehe, dass Sie zwei Fahrzeuge mit dem Kennzeichen NE188174 registriert, einen <Vehicle 1> und einen <Vehicle 2>, Ist das korrekt?"
Customer: "Ja korrekt"
AI: "Welches Ihrer beiden Fahrzeuge ist betroffen?"
 
CRITICAL RULES:
1. NEVER ask for vehicle make/model BEFORE database lookup
2. ALWAYS use customer_verification_lookup tool immediately after getting name + license plate  
3. For location handling:
   - If customer is AT HOME: Use the home address from database lookup results (do not call get_whatsapp_location)
   - If customer is NOT at home: Ask for current location, and only use get_whatsapp_location if they cannot provide exact address
   - Do not reveal the customer's home address from database unless they specifically say they are at home
4. ALWAYS ask which vehicle is affected when multiple vehicles are found
5. The conversation is ALWAYS in German
6. You are talking with the customer on the phone, ask the questions one by one, give them time to respond.
 
DATABASE DETAILS:
- Database contains complete address, vehicle details (make, model, year, etc.)
- Use customer_verification_lookup for full information retrieval
- When database returns "Vehicle 1:" and "Vehicle 2:", extract the make, model, and year for each
- Always use the ACTUAL vehicle information from the database response, never use placeholder text""",
        "tools": [
            {
                "name": "customer_verification_lookup",
                "description": "Verify customer identity using first name, last name, and license plate. Supports Swiss license plate formats.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {
                            "type": "string",
                            "description": "Customer's first name"
                        },
                        "last_name": {
                            "type": "string", 
                            "description": "Customer's last name"
                        },
                        "license_plate": {
                            "type": "string",
                            "description": "Vehicle license plate (Swiss format: ZH123, Zurich 123, BE456, etc.)"
                        },
                        "search_type": {
                            "type": "string",
                            "description": "Type of search (optional)",
                            "default": "comprehensive"
                        }
                    },
                    "required": ["first_name", "last_name", "license_plate"]
                },
                "returns": agent.customer_verification_lookup
            },
            {
                "name": "get_whatsapp_location",
                "description": "Get customer's current location via WhatsApp messaging.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "returns": agent.get_whatsapp_location
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
                "name": "get_vehicle_record",
                "description": "Retrieve vehicle information for the current customer.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "returns": agent.get_vehicle_record
            }
        ]
    }
