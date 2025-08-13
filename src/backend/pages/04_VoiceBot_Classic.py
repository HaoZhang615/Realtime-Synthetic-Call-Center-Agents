import streamlit as st
import os
import sys
import logging
import json
import requests
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Conditional imports for Azure Cosmos DB
try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False
    # Logger will be configured later, so we'll handle this in the function

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import common utilities
from utils import (
    setup_logging_and_monitoring, initialize_azure_clients,
    initialize_conversation, speech_to_text, text_to_speech, save_conversation_message,
    setup_sidebar_voice_controls,setup_sidebar_conversation_info,
    display_conversation_history, setup_page_header, setup_sidebar_header, setup_voice_input_recorder,
    setup_system_message_input, setup_voice_instruction_examples,
    create_chat_container, handle_audio_recording, initialize_session_messages,
    handle_chat_flow, ensure_fresh_conversation, get_current_datetime
)

# Import performance tracking
from utils.performance_metrics import PerformanceTracker, save_performance_metrics, analyze_customer_sentiment_from_conversation

# Configure logging and monitoring
setup_logging_and_monitoring()

logger = logging.getLogger(__name__)
logger.debug("Starting VoiceBot Classic page")

# Initialize Azure clients
client, token_provider, conversation_manager = initialize_azure_clients()

# Get Logic App URL for email sending
SEND_EMAIL_LOGIC_APP_URL = os.getenv("SEND_EMAIL_LOGIC_APP_URL")

# Database lookup function for roadside assistance
def database_lookups(params):
    """
    Look up customer and vehicle information from CosmosDB based on provided parameters.
    Supports the German phone call structure levels (Ebene 1-7).
    
    Args:
        params (dict): Search parameters including:
            - first_name: Customer first name
            - last_name: Customer last name
            - date_of_birth: Customer date of birth (optional)
            - license_plate: Vehicle license plate
            - phone_number: Customer phone number (optional)
            - search_type: Type of search ('customer', 'vehicle', 'comprehensive')
    
    Returns:
        str: Formatted search results with customer and vehicle information
    """
    if not COSMOS_AVAILABLE:
        logger.warning("Azure Cosmos DB dependencies not available")
        return "Datenbankdienst ist derzeit nicht verfügbar. Bitte fahren Sie mit der manuellen Datenerfassung fort oder wenden Sie sich an einen menschlichen Agenten."
    
    # Validate that we have either customer name or license plate
    has_customer_name = params.get("first_name") and params.get("last_name")
    has_license_plate = params.get("license_plate")
    
    if not has_customer_name and not has_license_plate:
        return "Für die Kundenverifikation benötige ich den Vor- und Nachnamen UND das Kennzeichen des Fahrzeugs. Können Sie mir bitte diese drei Informationen geben?"
    
    if has_customer_name and not has_license_plate:
        return "Ich habe Ihren Namen. Für die vollständige Verifikation benötige ich auch noch das Kennzeichen Ihres Fahrzeugs."
    
    if has_license_plate and not has_customer_name:
        return "Ich habe das Kennzeichen. Für die vollständige Verifikation benötige ich auch noch Ihren Vor- und Nachnamen."
    
    try:
        # Initialize Cosmos DB connection using existing conversation manager approach
        credential = DefaultAzureCredential()
        cosmos_endpoint = os.environ["COSMOSDB_ENDPOINT"]
        database_name = os.environ["COSMOSDB_DATABASE"]
        
        cosmos_client = CosmosClient(cosmos_endpoint, credential)
        database = cosmos_client.get_database_client(database_name)
        
        # Get container clients
        customer_container = database.get_container_client(os.environ["COSMOSDB_Customer_CONTAINER"])
        vehicles_container = database.get_container_client(os.environ.get("COSMOSDB_Vehicles_CONTAINER", "Vehicles"))
        
        search_results = {
            "customers": [],
            "vehicles": [],
            "summary": ""
        }
        
        # Ebene 1 - Customer identification search
        if params.get("first_name") and params.get("last_name"):
            customer_query = "SELECT * FROM c WHERE LOWER(c.first_name) = LOWER(@first_name) AND LOWER(c.last_name) = LOWER(@last_name)"
            customer_parameters = [
                {"name": "@first_name", "value": params["first_name"]},
                {"name": "@last_name", "value": params["last_name"]}
            ]
            
            # Add date of birth filter if provided
            if params.get("date_of_birth"):
                customer_query += " AND c.date_of_birth = @date_of_birth"
                customer_parameters.append({"name": "@date_of_birth", "value": params["date_of_birth"]})
            
            # Add phone number filter if provided
            if params.get("phone_number"):
                customer_query += " AND c.phone_number = @phone_number"
                customer_parameters.append({"name": "@phone_number", "value": params["phone_number"]})
            
            customers = list(customer_container.query_items(
                query=customer_query,
                parameters=customer_parameters,
                enable_cross_partition_query=True
            ))
            search_results["customers"] = customers
        
        # Vehicle search by license plate (Ebene 1 & 2)
        if params.get("license_plate"):
            vehicle_query = "SELECT * FROM c WHERE UPPER(REPLACE(c.license_plate, ' ', '')) = UPPER(REPLACE(@license_plate, ' ', ''))"
            vehicle_parameters = [{"name": "@license_plate", "value": params["license_plate"]}]
            
            vehicles = list(vehicles_container.query_items(
                query=vehicle_query,
                parameters=vehicle_parameters,
                enable_cross_partition_query=True
            ))
            search_results["vehicles"] = vehicles
        
        # If we have a customer ID, get their vehicles
        customer_ids = [c.get("customer_id") for c in search_results["customers"] if c.get("customer_id")]
        if customer_ids:
            for customer_id in customer_ids:
                customer_vehicles_query = "SELECT * FROM c WHERE c.customer_id = @customer_id"
                customer_vehicles = list(vehicles_container.query_items(
                    query=customer_vehicles_query,
                    parameters=[{"name": "@customer_id", "value": customer_id}],
                    enable_cross_partition_query=True
                ))
                search_results["vehicles"].extend(customer_vehicles)
        
        # Format results for agent use
        summary_parts = []
        
        if search_results["customers"]:
            summary_parts.append(f"KUNDEN GEFUNDEN ({len(search_results['customers'])}):")
            for customer in search_results["customers"]:
                customer_info = (f"- {customer.get('first_name', '')} {customer.get('last_name', '')}, "
                               f"geboren {customer.get('date_of_birth', 'unbekannt')}, "
                               f"Telefon: {customer.get('phone_number', 'unbekannt')}, "
                               f"Versicherungstyp: {customer.get('insurance_type', 'unbekannt')}, "
                               f"Adresse: {customer.get('address', {}).get('street', '')} {customer.get('address', {}).get('city', '')} {customer.get('address', {}).get('postal_code', '')}")
                summary_parts.append(customer_info)
        
        if search_results["vehicles"]:
            summary_parts.append(f"\nFAHRZEUGE GEFUNDEN ({len(search_results['vehicles'])}):")
            for vehicle_doc in search_results["vehicles"]:
                # Handle new vehicle structure with vehicles array
                if 'vehicles' in vehicle_doc and isinstance(vehicle_doc['vehicles'], list):
                    # New structure: document contains vehicles array
                    license_plate = vehicle_doc.get('license_plate', '')
                    customer_id = vehicle_doc.get('customer_id', '')
                    policy_number = vehicle_doc.get('policy_number', '')
                    
                    summary_parts.append(f"- Kennzeichen: {license_plate}, Kunde: {customer_id}, Policennummer: {policy_number}")
                    summary_parts.append(f"  {len(vehicle_doc['vehicles'])} Fahrzeuge registriert:")
                    
                    for i, vehicle in enumerate(vehicle_doc['vehicles'], 1):
                        vehicle_info = (f"    Fahrzeug {i}: {vehicle.get('make', '')} {vehicle.get('model', '')}, "
                                      f"Baujahr: {vehicle.get('year', '')}, "
                                      f"Farbe: {vehicle.get('color', '')}, "
                                      f"Kraftstoff: {vehicle.get('fuel_type', '')}, "
                                      f"Kilometerstand: {vehicle.get('mileage', 'unbekannt')} km")
                        summary_parts.append(vehicle_info)
                else:
                    # Old structure: individual vehicle documents (for backward compatibility)
                    vehicle_info = (f"- Kennzeichen: {vehicle_doc.get('license_plate', '')}, "
                                  f"Marke: {vehicle_doc.get('make', '')} {vehicle_doc.get('model', '')}, "
                                  f"Baujahr: {vehicle_doc.get('year', '')}, "
                                  f"Farbe: {vehicle_doc.get('color', '')}, "
                                  f"Kraftstoff: {vehicle_doc.get('fuel_type', '')}, "
                                  f"Kilometerstand: {vehicle_doc.get('mileage', 'unbekannt')} km, "
                                  f"Policennummer: {vehicle_doc.get('policy_number', 'unbekannt')}, "
                                  f"Kunde: {vehicle_doc.get('customer_id', 'unbekannt')}")
                    summary_parts.append(vehicle_info)
        
        if not any([search_results["customers"], search_results["vehicles"]]):
            summary_parts.append("KEINE TREFFER GEFUNDEN - Bitte überprüfen Sie die eingegebenen Daten oder fragen Sie nach weiteren Identifikationsmerkmalen.")
        
        search_results["summary"] = "\n".join(summary_parts)
        
        logger.info(f"Database lookup completed. Found: {len(search_results['customers'])} customers, {len(search_results['vehicles'])} vehicles")
        
        return search_results["summary"]
        
    except Exception as e:
        logger.error(f"Database lookup error: {e}")
        return f"Fehler bei der Datenbankabfrage: {str(e)}. Bitte versuchen Sie es erneut oder wenden Sie sich an einen menschlichen Agenten."

# Email sending function
def send_email(params):
    """Send an email using Azure Logic App."""
    try:
        if not SEND_EMAIL_LOGIC_APP_URL:
            return "Email service is not configured. Please contact administrator."
        
        res = requests.post(SEND_EMAIL_LOGIC_APP_URL, json=params)
        res.raise_for_status()
        return "Email sent successfully."
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return f"Failed to send email: {e}"

# Ensure a fresh conversation for this page (resets if coming from a different page)
ensure_fresh_conversation("04")

# Initialize performance tracker
if "performance_tracker" not in st.session_state:
    st.session_state.performance_tracker = PerformanceTracker()
    st.session_state.performance_tracker.start_session()

# Get all available model deployment names
available_models = {}
try:
    available_models["gpt-4o"] = os.environ.get("AZURE_OPENAI_GPT4o_DEPLOYMENT")
    available_models["gpt-4o-mini"] = os.environ.get("AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT")
    available_models["gpt-4.1"] = os.environ.get("AZURE_OPENAI_GPT41_DEPLOYMENT")
    available_models["gpt-4.1-mini"] = os.environ.get("AZURE_OPENAI_GPT41_MINI_DEPLOYMENT")
    available_models["gpt-4.1-nano"] = os.environ.get("AZURE_OPENAI_GPT41_NANO_DEPLOYMENT")
    
    # Filter out None values (models not available)
    available_models = {k: v for k, v in available_models.items() if v is not None}
    
except Exception as e:
    logger.warning(f"Error loading models: {e}")
    # Fallback to just gpt-4o-mini if there's an issue
    available_models = {"gpt-4o-mini": os.environ.get("AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT", "gpt-4o-mini")}

# Default model deployment name (keeping backward compatibility)
gpt4omini = os.environ.get("AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT", "gpt-4o-mini")

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Removed local JSON schema + summary functions now centralized in voicebot_common

# Basic chat function with email sending capability
def basic_chat(user_request, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
        
    # Start tracking response latency
    st.session_state.performance_tracker.start_response_timing()
    st.session_state.performance_tracker.increment_message_count()
        
    # Use the system message from session state
    system_message = st.session_state.system_message
    
    # Add current datetime to the system message (invisible to user)
    system_message_with_datetime = f"Current date and time: {get_current_datetime()}\n\n{system_message}"
    
    # Get the selected model deployment name
    selected_model_deployment = st.session_state.get("selected_model_deployment", gpt4omini)
    
    # Update model parameters for tracking
    temperature = st.session_state.get("temperature", 0.7)
    st.session_state.performance_tracker.update_model_parameters(temperature, system_message_with_datetime, selected_model_deployment)
    
    # Update system message with the current JSON template if needed
    if "json_template" in st.session_state and st.session_state.json_template:
        # Remove any existing JSON template section from the system message
        if "```json" in system_message_with_datetime:
            # Find start and end of the JSON template in the system message
            json_start = system_message_with_datetime.find("Use the following JSON template")
            if json_start > 0:
                system_message_with_datetime = system_message_with_datetime[:json_start].strip()
        
        # Add the current JSON template
        system_message_with_datetime += f"\n\nUse the following JSON template for structured data collection:\n```json\n{st.session_state.json_template}\n```"
    
    messages = [
        {
            "role": "system",
            "content": system_message_with_datetime,
        }
    ]
    # Add previous conversation history
    messages.extend(conversation_history)
    # Add current user request
    messages.append({"role": "user", "content": user_request})
    
    # Define available tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send an email to the specified recipient with subject and body content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "The recipient's email address."
                        },
                        "subject": {
                            "type": "string",
                            "description": "The subject of the email."
                        },
                        "body": {
                            "type": "string",
                            "description": "The body content of the email."
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        }
    ]
    
    # Add database lookup tool if Cosmos DB is available
    if COSMOS_AVAILABLE:
        tools.append({
            "type": "function",
            "function": {
                "name": "database_lookups",
                "description": "CRITICAL FUNCTION: Look up and verify customer identity using first name, last name, and license plate. This function returns COMPLETE customer profiles including living address, phone number, email, and vehicle details (make, model, year, color, policy number). Use this immediately when you have customer's full name and license plate to verify their identity and get complete context for the conversation. Each customer has exactly 2 vehicles sharing the same license plate.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {
                            "type": "string",
                            "description": "Customer's first name (Vorname) - REQUIRED for verification workflow"
                        },
                        "last_name": {
                            "type": "string",
                            "description": "Customer's last name (Nachname) - REQUIRED for verification workflow"
                        },
                        "license_plate": {
                            "type": "string",
                            "description": "Vehicle license plate number (Kennzeichen) - REQUIRED for verification workflow"
                        },
                        "date_of_birth": {
                            "type": "string",
                            "description": "Customer's date of birth (Geburtsdatum) in YYYY-MM-DD format - Optional for additional verification"
                        },
                        "phone_number": {
                            "type": "string",
                            "description": "Customer's phone number for additional verification - Optional"
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["customer", "vehicle", "comprehensive"],
                            "description": "Use 'comprehensive' for complete customer verification and information retrieval"
                        }
                    },
                    "required": []
                }
            }
        })
    
    try:
        response = client.chat.completions.create(
            model=selected_model_deployment,
            store=True,  # Store the response for performance tracking
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=800,
        )
        
        # End response timing
        st.session_state.performance_tracker.end_response_timing()
        
        # Handle the response
        assistant_message = response.choices[0].message
        tool_calls_log = []  # For logging tool calls to CosmosDB
        
        # Check if the assistant wants to call a function
        if assistant_message.tool_calls:
            # Add the assistant message to conversation history
            messages.append(assistant_message)
            
            # Process tool calls
            for tool_call in assistant_message.tool_calls:
                function_result = None
                
                if tool_call.function.name == "send_email":
                    # Parse function arguments
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Call the send_email function
                    function_result = send_email(function_args)
                    
                elif tool_call.function.name == "database_lookups":
                    # Parse function arguments
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Call the database_lookups function
                    function_result = database_lookups(function_args)
                
                if function_result:
                    # Log tool call for evaluation purposes
                    tool_call_log = {
                        "tool_call_id": tool_call.id,
                        "function_name": tool_call.function.name,
                        "function_arguments": function_args,
                        "function_result": function_result,
                        "timestamp": get_current_datetime(),
                        "success": "Fehler" not in function_result.lower() and "error" not in function_result.lower()
                    }
                    tool_calls_log.append(tool_call_log)
                    
                    # Add tool result to messages
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": function_result
                    }
                    messages.append(tool_message)
            
            # Get final response after tool execution
            final_response = client.chat.completions.create(
                model=selected_model_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=4000,
            )
            
            assistant_response = final_response.choices[0].message.content
        else:
            assistant_response = assistant_message.content
        
        # Save conversation to Cosmos DB using common utility with tool calls
        save_conversation_message(
            user_request, 
            assistant_response, 
            conversation_manager,
            tool_calls=tool_calls_log if tool_calls_log else None
        )
        
        return assistant_response
        
    except Exception as e:
        st.session_state.performance_tracker.end_response_timing()
        logger.error(f"Error in basic_chat: {e}")
        raise
# Set up page header
setup_page_header("Azure OpenAI powered Self Service Chatbot")

# Initialize conversation on page load with voicebot type
initialize_conversation(conversation_manager, voicebot_type="classic")

# Set up sidebar configuration
setup_sidebar_header()

# Voice controls
voice_on, selected_voice, tts_instructions = setup_sidebar_voice_controls()

# Voice instruction examples
setup_voice_instruction_examples()

setup_sidebar_conversation_info()

# Voice input recorder
custom_audio_bytes = setup_voice_input_recorder()

# Wrapper functions for performance tracking
def tracked_speech_to_text(audio_bytes):
    """Speech-to-text with performance tracking."""
    st.session_state.performance_tracker.start_speech_to_text()
    try:
        result = speech_to_text(audio_bytes, client)
        st.session_state.performance_tracker.end_speech_to_text()
        return result
    except Exception as e:
        st.session_state.performance_tracker.end_speech_to_text()
        raise

def tracked_text_to_speech(text):
    """Text-to-speech with performance tracking."""
    st.session_state.performance_tracker.start_text_to_speech()
    try:
        result = text_to_speech(text, client)
        st.session_state.performance_tracker.end_text_to_speech()
        return result
    except Exception as e:
        st.session_state.performance_tracker.end_text_to_speech()
        raise

# Default JSON template for structured data collection
default_json_template = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Car Insurance Claim",
  "type": "object",
  "properties": {
    "personalInfo": {
      "type": "object",
      "properties": {
        "firstName": { "type": "string" },
        "lastName": { "type": "string" },
        "birthDate": { "type": "string", "format": "date" }
      },
      "required": ["firstName", "lastName"]
    },
    "vehicleInfo": {
      "type": "object",
      "properties": {
        "plateNumber": { "type": "string" },
        "brand": { "type": "string" },
        "model": { "type": "string" }
      },
      "required": ["plateNumber"]
    },
    "incidentInfo": {
      "type": "object",
      "properties": {
        "causeDescription": {"type": "string"},
        "location": { "type": "string",
                      "description": "Vehicle location: If customer is at home, use their actual street address from database (e.g., 'Bahnhofstrasse 10, Basel'). Otherwise gather enough info to understand where the vehicle is located."},
    "nrOfAdultsInCarForTowing": { "type": "integer" },
    "nrOfChildrenInCarForTowing": { "type": "integer" },
        "isItUrgent": { "type": "boolean" },
        "otherRelevantInfoForAssistance": { "type": "string" }
      },
      "required": ["causeDescription", "location", "isItUrgent", "otherRelevantInfoForAssistance"]
    }
  },
  "required": ["personalInfo", "vehicleInfo", "incidentInfo"]
}
"""
# System message configuration
default_system_message = """You are a voice-based AI agent for Mobi 24 roadside assistance. CRITICAL: You MUST follow this exact workflow for customer verification.

MANDATORY WORKFLOW - FOLLOW EXACTLY:

STEP 1 - COLLECT IDENTIFICATION (DO NOT ASK FOR VEHICLE DETAILS YET):
- Ask for customer's first name (Vorname)  
- Ask for customer's last name (Nachname)
- Ask for license plate number (Kennzeichen)
- DO NOT ask for vehicle make/model/details - these come from the database

STEP 2 - IMMEDIATE DATABASE VERIFICATION (CRITICAL):
- IMMEDIATELY call database_lookups function with first_name, last_name, and license_plate
- This is MANDATORY - do not proceed without this step
- The database contains ALL vehicle and customer information

STEP 3 - VERIFY AND CONFIRM WITH CUSTOMER:
- If database returns results: "Vielen Dank! Ich habe Ihre Daten gefunden. Sie sind [name] und wohnen an der [address from database]. Sie haben zwei Fahrzeuge mit dem Kennzeichen [plate] registriert. Ist das korrekt?"
- If no database match: "Ich kann keine Kundendaten mit diesen Angaben finden. Bitte überprüfen Sie die Schreibweise Ihres Namens und Kennzeichens."

STEP 4 - VEHICLE SELECTION (WHEN MULTIPLE VEHICLES FOUND):
- ALWAYS present both vehicles clearly using the ACTUAL vehicle details from the database lookup
- Use the format: "Welches Ihrer beiden Fahrzeuge ist betroffen? Sie haben einen [actual make model from database] aus [actual year] und einen [actual make model from database] aus [actual year] registriert."
- Wait for customer to specify which vehicle has the problem
- Example: "Welches Ihrer beiden Fahrzeuge ist betroffen? Sie haben einen Peugeot Standard aus 2022 und einen Honda Standard aus 2023 registriert."

STEP 5 - ONLY AFTER VEHICLE SELECTION:
- Proceed with breakdown questions for the SPECIFIC vehicle chosen
- Ask about the problem/breakdown cause
- Ask about location of the vehicle
- IMPORTANT: If customer is at home, use the database lookup tool to extract their ACTUAL ADDRESS, not the literal phrase "zu Hause"

STEP 6 - FINAL CONFIRMATION
- Before ending the conversation, always confirm the details with the customer
- Wait for customer confirmation before closing the conversation
- close the conversation by letting the user know they will soon be directed to the human agent while enjoying the waiting music.

CRITICAL RULES:
1. NEVER ask for vehicle make/model BEFORE database lookup
2. ALWAYS call database_lookups immediately after getting name + license plate  
3. ALWAYS reference the customer's address from database to confirm identity
4. ALWAYS ask which vehicle is affected when multiple vehicles are found
5. When customer says "at home", record their actual street address from database, not "zu Hause"
6. The conversation is ALWAYS in German

EXAMPLE CORRECT FLOW:
Customer: "Mein Auto springt nicht an"
AI: "Guten Tag! Ich helfe Ihnen gerne. Können Sie mir bitte Ihren Vor- und Nachnamen nennen?"
Customer: "Georg Baumann"
AI: "Und das Kennzeichen Ihres Fahrzeugs?"
Customer: "NE188174"  
AI: [CALLS database_lookups immediately]
AI: "Vielen Dank! Ich habe Ihre Daten gefunden. Sie sind Georg Baumann und wohnen an der Bahnhofstrasse 10 in Basel. Sie haben zwei Fahrzeuge mit dem Kennzeichen NE188174 registriert. Ist das korrekt?"
Customer: "Ja korrekt"
AI: "Welches Ihrer beiden Fahrzeuge ist betroffen? Sie haben einen [make1 model1] und einen [make2 model2] registriert."

DATABASE DETAILS:
- Every customer has exactly 2 vehicles with the same license plate
- Database contains complete address, vehicle details (make, model, year, etc.)
- Use search_type="comprehensive" for full information retrieval
- When database returns "Fahrzeug 1:" and "Fahrzeug 2:", extract the make, model, and year for each
- Always use the ACTUAL vehicle information from the database response, never use placeholder text"""

# Add JSON template input to sidebar
with st.sidebar:
    # Model selection
    st.subheader("🤖 Model Selection")
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "gpt-4o-mini"  # Default to gpt-4o-mini
    
    # Create dropdown for model selection
    if available_models:
        st.session_state.selected_model = st.selectbox(
            "Choose AI Model:",
            options=list(available_models.keys()),
            index=list(available_models.keys()).index(st.session_state.selected_model) 
                  if st.session_state.selected_model in available_models else 0,
            help="Select the AI model to use for conversation"
        )
        
        # Store the deployment name for the selected model
        st.session_state.selected_model_deployment = available_models[st.session_state.selected_model]
        
        # Show some info about the selected model
        model_descriptions = {
            "gpt-4o": "Latest GPT-4o model - Most capable, slower response",
            "gpt-4o-mini": "Lightweight GPT-4o - Fast and efficient",
            "gpt-4.1": "GPT-4.1 model - Advanced reasoning capabilities",
            "gpt-4.1-mini": "GPT-4.1 mini - Balanced performance and speed",
            "gpt-4.1-nano": "GPT-4.1 nano - Fastest response, basic capabilities"
        }
        
        if st.session_state.selected_model in model_descriptions:
            st.caption(model_descriptions[st.session_state.selected_model])
            
        st.info(f"Using deployment: `{st.session_state.selected_model_deployment}`")
    else:
        st.error("No models available. Check environment configuration.")
        st.session_state.selected_model_deployment = gpt4omini
    
    # Temperature control
    st.subheader("🎛️ Model Settings")
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.1
    
    st.session_state.temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.temperature,
        step=0.1,
        help="Controls randomness: 0.0 = deterministic, 1.0 = very creative"
    )
    
    
    # Add separator
    st.markdown("---")
    
    st.subheader("🧪 Test Scenario Instructions")
    with st.expander("📋 How to Test the AI Agent"):
        st.write("""
        **Test Steps:**
        
        1. **Start Conversation**: 
           - Say "Hallo, ich brauche Hilfe" or similar
           
        2. **Provide Information When Asked**:
           - First name (Vorname): Use any Swiss name from database
           - Last name (Nachname): Use corresponding surname  
           - License plate (Kennzeichen): Use format like ZH123456, BE789012, etc.
           
        3. **Observe AI Behavior**:
           - ✅ AI should call database_lookups function
           - ✅ AI should reference your address from database
           - ✅ AI should mention vehicle details (make, model)
           - ✅ AI should show it has your complete information
           
        4. **Expected AI Response Example**:
           - "I can see you're calling from Bahnhofstrasse 42, Zürich..."
           - "You have a BMW 3er and a Mercedes C-Class registered under this plate..."
           - "Your policy number is 54321..."
           
        **Note**: The database contains synthetic Swiss customer data with realistic addresses and vehicle information.
        """)
    
    # Database status
    st.subheader("🗄️ Database Status")
    if COSMOS_AVAILABLE:
        st.success("✅ Database lookups available")
        st.caption("Agent can lookup customer and vehicle information")
        
        # Add info about database lookup
        with st.expander("ℹ️ Test Scenario Workflow"):
            st.write("""
            **Expected Test Flow:**
            
            1. **Customer Identification**
               - AI asks for first name (Vorname)
               - AI asks for last name (Nachname)  
               - AI asks for license plate (Kennzeichen)
            
            2. **Database Verification**
               - AI calls database_lookups with all 3 pieces
               - System verifies customer exists
               - Returns complete customer profile + vehicle details
            
            3. **Information Confirmation**
               - AI references customer's address from database
               - AI confirms vehicle details (make, model, etc.)
               - AI uses this context for rest of conversation
            
            **What Database Returns:**
            - Complete customer address (street, city, postal code)
            - Phone number and email
            - 2 vehicles with same license plate
            - Vehicle details: make, model, year, color, VIN
            - Policy numbers embedded in vehicle records
            
            **Current Data Structure:**
            - Each customer = exactly 2 vehicles
            - Both vehicles = same license plate  
            - Both vehicles = same policy number
            - Different makes/models/colors allowed
            """)
    else:
        st.warning("⚠️ Database lookups unavailable")
        st.caption("Agent will use manual data collection only")
    
    system_message = setup_system_message_input(default_system_message)

    st.subheader("📋 JSON Template")
    if "json_template" not in st.session_state:
        st.session_state.json_template = default_json_template
    
    st.session_state.json_template = st.text_area(
        "Structured Data Template:",
        value=st.session_state.json_template,
        height=300,
        help="This JSON template will be used to structure the data collected during the conversation."
    )
    
    # Validate the JSON template and show status
    try:
        json.loads(st.session_state.json_template)
        st.success("✅ Valid JSON template")
        
        # Test dynamic model creation
        # Attempt dynamic model creation using shared utility
        from utils.voicebot_common import create_dynamic_pydantic_model, generate_conversation_summary as shared_generate_summary
        test_model = create_dynamic_pydantic_model(st.session_state.json_template)
        if test_model:
            st.info("🎯 Template ready for dynamic structured outputs")
        else:
            st.error("❌ Template cannot be used for structured outputs")
            
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON format")
    except Exception as e:
        st.error(f"❌ Template error: {str(e)}")
    
    # Add a small note about how the template is used
    st.caption("This template will be dynamically converted to a Pydantic model for structured outputs.")
    # Finish Conversation section
    st.subheader("🏁 Finish Conversation")
    st.caption("Generate a structured JSON summary and save performance metrics.")
    
    if st.button("📋 Generate JSON Summary", type="primary"):
        # Set a flag to indicate we're generating summary (prevents message processing)
        st.session_state.generating_summary = True
        
        from utils.voicebot_common import generate_conversation_summary as shared_generate_summary
        
        # Get the selected model deployment name
        selected_model_deployment = st.session_state.get("selected_model_deployment", gpt4omini)
        
        # Analyze customer sentiment from conversation history
        if "messages" in st.session_state and st.session_state.messages:
            try:
                sentiment_score = analyze_customer_sentiment_from_conversation(
                    client, selected_model_deployment, st.session_state.messages
                )
                st.session_state.performance_tracker.set_customer_sentiment(sentiment_score)
                st.success(f"Customer sentiment analyzed: {sentiment_score}/5")
            except Exception as e:
                logger.error(f"Error analyzing sentiment: {e}")
                st.warning("Could not analyze customer sentiment")
        
        # End session tracking
        st.session_state.performance_tracker.end_session()
        
        # Save performance metrics to conversation document
        if "conversation_doc" in st.session_state and st.session_state.conversation_doc:
            logger.info(f"Saving performance metrics to conversation: {st.session_state.conversation_doc.get('id', 'unknown')}")
            save_performance_metrics(st.session_state.conversation_doc, st.session_state.performance_tracker)
            logger.info(f"Performance metrics saved. Document keys: {list(st.session_state.conversation_doc.keys())}")
            
            # Save updated conversation with metrics to CosmosDB
            try:
                conversation_manager.save_conversation(st.session_state.conversation_doc)
                st.success("Performance metrics saved to CosmosDB")
                logger.info("Successfully saved conversation with metrics to CosmosDB")
            except Exception as e:
                logger.error(f"Error saving conversation with metrics: {e}")
                st.error("Could not save performance metrics")
        else:
            logger.warning("No conversation document found to save metrics")
            st.warning("No conversation document found to save metrics")
        
        # Generate the JSON summary with custom extraction message for location handling
        custom_extraction_message = """You are a data extraction expert specializing in extracting structured information from roadside assistance conversations. 

CRITICAL LOCATION RULES:
- If the customer is at home, you MUST extract their actual street address from the database information that was provided during the conversation
- NEVER use "zu Hause" or "at home" as the location value
- Look for the customer's address that was mentioned when the agent verified their identity (e.g., "Sie wohnen an der Bahnhofstrasse 10 in Basel")
- Use the complete street address including street name, number, and city

For any other information not mentioned or unclear, use null values. Extract information accurately and always use the customer's actual street address when they mention being at home."""
        
        try:
            shared_generate_summary(client, selected_model_deployment, conversation_manager, st.session_state.json_template, custom_extraction_message)
        except Exception as e:
            st.error(f"Error generating summary: {e}")
            logger.error(f"Summary generation failed: {e}")


# Handle audio recording
if custom_audio_bytes:
    handle_audio_recording(custom_audio_bytes, tracked_speech_to_text)

# Initialize session messages
initialize_session_messages()

# Create conversation container
conversation_container = create_chat_container(600)

# Handle new message input
# Skip message processing if we're generating a summary
if st.session_state.get("generating_summary", False):
    # Clear the flag and don't process any messages
    st.session_state.generating_summary = False
    prompt = None
elif text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
elif "voice_prompt" in st.session_state:
    prompt = st.session_state.voice_prompt
    del st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        # Use the common chat flow handler with tracked TTS
        handle_chat_flow(prompt, basic_chat, voice_on, tracked_text_to_speech)
    else:
        # Display existing conversation
        display_conversation_history(st.session_state.messages)