"""
Tool definitions for VoiceBot Classic.
Contains function definitions for AI tool calls including database lookups and email sending.
"""

import os
import logging

logger = logging.getLogger(__name__)

def get_email_tool_definition():
    """Returns the email tool definition for AI function calling."""
    return {
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

def get_database_lookup_tool_definition():
    """Returns the database lookup tool definition for AI function calling."""
    return {
        "type": "function",
        "function": {
            "name": "database_lookups",
            "description": "CRITICAL FUNCTION: Look up and verify customer identity using first name, last name, and license plate. This function returns COMPLETE customer profiles including HOME/LIVING ADDRESS (use this when customer says they are 'at home'), phone number, email, and vehicle details (make, model, year, color, policy number). Use this immediately when you have customer's full name and license plate to verify their identity and get complete context for the conversation. Each customer has exactly 2 vehicles sharing the same license plate. The returned address is the customer's registered home address.",
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
    }

def get_geo_location_tool_definition():
    """Returns the geolocation tool definition for AI function calling."""
    return {
        "type": "function",
        "function": {
            "name": "get_geo_location",
            "description": "Get the geographical location from the user via WhatsApp. IMPORTANT: Only use this function when: 1) User is NOT at home/their registered address, 2) User cannot provide a clear address verbally, 3) Emergency situation requiring exact coordinates. DO NOT use if user says they are 'at home' and you have their home address from database lookup. DO NOT use for routine breakdown assistance when user is at their registered address.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
                },
            }
        }

def get_available_tools(cosmos_available=False):
    """
    Returns list of available tools based on system capabilities.
    
    Args:
        cosmos_available (bool): Whether Cosmos DB is available for database lookups
        
    Returns:
        list: List of tool definitions for AI function calling
    """
    tools = [get_email_tool_definition(), get_geo_location_tool_definition()]
    
    if cosmos_available:
        tools.append(get_database_lookup_tool_definition())
        logger.info("Database lookup tool added to available tools")
    else:
        logger.warning("Database lookup tool not available - Cosmos DB unavailable")
    
    return tools
