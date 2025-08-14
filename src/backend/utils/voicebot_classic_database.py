"""
Database operations for VoiceBot Classic.
Contains functions for customer and vehicle lookups from CosmosDB.
"""

import os
import re
import logging
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Conditional imports for Azure Cosmos DB
try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False
    logger.warning("Azure Cosmos DB dependencies not available")

def normalize_swiss_license_plate(plate_number: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize Swiss license plate for flexible matching.
    Swiss format: Canton letters (1-2 chars) + Numbers (1-6 digits)
    Also handles full canton names + numbers (e.g., "Zurich 123" -> "ZH123")
    
    Examples: ZH1, ZH123, BE456789, AG42, "Zurich 123", "Bern 456"
    
    Args:
        plate_number (str): Input license plate
        
    Returns:
        tuple: (canton_code, number_part) or (None, None) if invalid
    """
    if not plate_number:
        return None, None
    
    # Swiss canton name to code mapping
    canton_mapping = {
        # German names
        'ZURICH': 'ZH', 'ZÜRICH': 'ZH',
        'BERN': 'BE', 'BERNE': 'BE',
        'LUZERN': 'LU', 'LUCERNE': 'LU',
        'URI': 'UR',
        'SCHWYZ': 'SZ',
        'OBWALDEN': 'OW',
        'NIDWALDEN': 'NW',
        'GLARUS': 'GL',
        'ZUG': 'ZG',
        'FREIBURG': 'FR', 'FRIBOURG': 'FR',
        'SOLOTHURN': 'SO', 'SOLEURE': 'SO',
        'BASEL-STADT': 'BS', 'BASEL STADT': 'BS', 'BASEL': 'BS',
        'BASEL-LANDSCHAFT': 'BL', 'BASEL LANDSCHAFT': 'BL', 'BASELLAND': 'BL',
        'SCHAFFHAUSEN': 'SH',
        'APPENZELL AUSSERRHODEN': 'AR', 'APPENZELL-AUSSERRHODEN': 'AR', 'APPENZELL': 'AR',
        'APPENZELL INNERRHODEN': 'AI', 'APPENZELL-INNERRHODEN': 'AI',
        'SANKT GALLEN': 'SG', 'ST GALLEN': 'SG', 'ST. GALLEN': 'SG', 'SAINT GALLEN': 'SG',
        'GRAUBÜNDEN': 'GR', 'GRAUBUENDEN': 'GR', 'GRISONS': 'GR',
        'AARGAU': 'AG',
        'THURGAU': 'TG',
        'TESSIN': 'TI', 'TICINO': 'TI',
        'WAADT': 'VD', 'VAUD': 'VD',
        'WALLIS': 'VS', 'VALAIS': 'VS',
        'NEUENBURG': 'NE', 'NEUCHATEL': 'NE', 'NEUCHÂTEL': 'NE',
        'GENF': 'GE', 'GENEVA': 'GE', 'GENÈVE': 'GE', 'GENEVE': 'GE',
        'JURA': 'JU'
    }
    
    # Remove spaces and convert to uppercase for processing
    clean_input = plate_number.strip().upper()
    
    # Try to match full canton name + number pattern first
    # Pattern: "CANTON_NAME NUMBER" (e.g., "ZURICH 123", "BERN 456")
    for canton_name, canton_code in canton_mapping.items():
        # Pattern: canton name followed by space and 1-6 digits
        pattern = rf'^{re.escape(canton_name)}\s+(\d{{1,6}})$'
        match = re.match(pattern, clean_input)
        if match:
            number_part = match.group(1)
            return canton_code, number_part
        
        # Also try without space: "ZURICH123"
        pattern_no_space = rf'^{re.escape(canton_name)}(\d{{1,6}})$'
        match_no_space = re.match(pattern_no_space, clean_input)
        if match_no_space:
            number_part = match_no_space.group(1)
            return canton_code, number_part
    
    # If no full canton name match, try standard 1-2 letter code + number
    # Remove spaces and convert to uppercase
    clean_plate = clean_input.replace(" ", "")
    
    # Swiss canton codes (1-2 letters) followed by 1-6 digits
    match = re.match(r'^([A-Z]{1,2})(\d{1,6})$', clean_plate)
    
    if match:
        canton_code = match.group(1)
        number_part = match.group(2)
        
        # Validate that it's a real Swiss canton code
        valid_canton_codes = set(canton_mapping.values())
        if canton_code in valid_canton_codes:
            return canton_code, number_part
    
    return None, None

def database_lookups(params: Dict[str, Any]) -> str:
    """
    Look up customer and vehicle information from CosmosDB based on provided parameters.
    Supports the German phone call structure levels (Ebene 1-7).
    
    Args:
        params (dict): Search parameters including:
            - first_name: Customer first name
            - last_name: Customer last name
            - license_plate: Vehicle license plate
            - search_type: Type of search ('customer', 'vehicle', 'comprehensive')
    
    Returns:
        str: Formatted search results with customer and vehicle information
    """
    if not COSMOS_AVAILABLE:
        logger.warning("Azure Cosmos DB dependencies not available")
        return "Database service is currently unavailable. Please proceed with manual data collection or contact a human agent."
    
    # Validate that we have either customer name or license plate
    has_customer_name = params.get("first_name") and params.get("last_name")
    has_license_plate = params.get("license_plate")
    
    if not has_customer_name and not has_license_plate:
        return "For customer verification I need the first and last name AND the license plate of the vehicle. Can you please provide me with these three pieces of information?"
    
    if has_customer_name and not has_license_plate:
        return "I have your name. For complete verification I also need the license plate of your vehicle."
    
    if has_license_plate and not has_customer_name:
        return "I have the license plate. For complete verification I also need your first and last name."
    
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
        
        # STRICT VERIFICATION: Both name and license plate must match the same customer
        if params.get("first_name") and params.get("last_name") and params.get("license_plate"):
            # Normalize the input license plate for Swiss format matching
            input_canton, input_number = normalize_swiss_license_plate(params["license_plate"])
            
            if not input_canton or not input_number:
                # Invalid license plate format
                search_results["vehicles"] = []
                search_results["customers"] = []
                logger.warning(f"Invalid Swiss license plate format: {params['license_plate']}")
            else:
                # Swiss license plate flexible matching query
                # This will match plates where the normalized format matches the input
                vehicle_query = """
                    SELECT * FROM c 
                    WHERE UPPER(REPLACE(c.license_plate, ' ', '')) = UPPER(@normalized_plate)
                       OR UPPER(REPLACE(c.license_plate, ' ', '')) = UPPER(@plate_with_spaces)
                       OR UPPER(REPLACE(c.license_plate, ' ', '')) = UPPER(@canton_number)
                """
                
                # Generate multiple possible formats for matching
                normalized_plate = f"{input_canton}{input_number}"
                plate_with_spaces = f"{input_canton} {input_number}"
                
                vehicle_parameters = [
                    {"name": "@normalized_plate", "value": normalized_plate},
                    {"name": "@plate_with_spaces", "value": plate_with_spaces}, 
                    {"name": "@canton_number", "value": params["license_plate"]}
                ]
                
                vehicles_by_plate = list(vehicles_container.query_items(
                    query=vehicle_query,
                    parameters=vehicle_parameters,
                    enable_cross_partition_query=True
                ))
                
                # If no vehicles found by license plate, return no match immediately
                if not vehicles_by_plate:
                    search_results["vehicles"] = []
                    search_results["customers"] = []
                else:
                    # Get customer IDs from vehicles found by license plate
                    customer_ids_from_vehicles = []
                    for vehicle_doc in vehicles_by_plate:
                        if vehicle_doc.get("customer_id"):
                            customer_ids_from_vehicles.append(vehicle_doc["customer_id"])
                    
                    # Now verify that the customer name matches one of these customer IDs
                    valid_customers = []
                    for customer_id in customer_ids_from_vehicles:
                        customer_query = """SELECT * FROM c WHERE c.customer_id = @customer_id 
                                           AND LOWER(c.first_name) = LOWER(@first_name) 
                                           AND LOWER(c.last_name) = LOWER(@last_name)"""
                        customer_parameters = [
                            {"name": "@customer_id", "value": customer_id},
                            {"name": "@first_name", "value": params["first_name"]},
                            {"name": "@last_name", "value": params["last_name"]}
                        ]

                        
                        matching_customers = list(customer_container.query_items(
                            query=customer_query,
                            parameters=customer_parameters,
                            enable_cross_partition_query=True
                        ))
                        valid_customers.extend(matching_customers)
                    
                    # Only include vehicles if we found matching customers
                    if valid_customers:
                        search_results["customers"] = valid_customers
                        # Only include vehicles that belong to verified customers
                        verified_customer_ids = [c.get("customer_id") for c in valid_customers]
                        search_results["vehicles"] = [v for v in vehicles_by_plate 
                                                    if v.get("customer_id") in verified_customer_ids]
                    else:
                        # Name and license plate don't belong to the same customer
                        search_results["vehicles"] = []
                        search_results["customers"] = []
        
        # Format results for agent use - simplified and clean
        summary_parts = []
        
        if search_results["customers"]:
            # Customer information - only name and address
            customer = search_results["customers"][0]  # Take first customer (should only be one)
            name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}"
            address = customer.get('address', {})
            address_str = f"{address.get('street', '')}, {address.get('city', '')}, {address.get('postal_code', '')}"
            
            summary_parts.append(f"Customer: {name}")
            summary_parts.append(f"Address: {address_str}")
        
        if search_results["vehicles"]:
            # Vehicle information - only make, model, year, color (max 2 vehicles as requested)
            vehicle_count = 0
            for vehicle_doc in search_results["vehicles"]:
                if vehicle_count >= 2:  # Limit to 2 vehicles as requested
                    break
                    
                # Handle new vehicle structure with vehicles array
                if 'vehicles' in vehicle_doc and isinstance(vehicle_doc['vehicles'], list):
                    # New structure: document contains vehicles array
                    for vehicle in vehicle_doc['vehicles']:
                        if vehicle_count >= 2:
                            break
                        vehicle_count += 1
                        
                        make = vehicle.get('make', '').strip()
                        model = vehicle.get('model', '').strip()
                        year = vehicle.get('year', '')
                        color = vehicle.get('color', '').strip()
                        
                        summary_parts.append(f"Vehicle {vehicle_count}: {make} {model} ({year}, {color})")
                else:
                    # Old structure: individual vehicle documents
                    vehicle_count += 1
                    make = vehicle_doc.get('make', '').strip()
                    model = vehicle_doc.get('model', '').strip()
                    year = vehicle_doc.get('year', '')
                    color = vehicle_doc.get('color', '').strip()
                    
                    summary_parts.append(f"Vehicle {vehicle_count}: {make} {model} ({year}, {color})")
        
        if not any([search_results["customers"], search_results["vehicles"]]):
            # Check if we have both name and license plate but no match
            if params.get("first_name") and params.get("last_name") and params.get("license_plate"):
                summary_parts.append("No matching customer found with the provided name and license plate.")
                summary_parts.append("Please verify the information and try again.")
            else:
                summary_parts.append("No customer data found. Please provide complete information.")
        
        search_results["summary"] = "\n".join(summary_parts)
        
        logger.info(f"Database lookup completed. Found: {len(search_results['customers'])} customers, {len(search_results['vehicles'])} vehicles")
        logger.info(f"Database lookup summary provided to AI agent:\n{search_results['summary']}")
        return search_results["summary"]
    except Exception as e:
        logger.error(f"Database lookup error: {e}")
        return f"Database query error: {str(e)}. Please try again or contact a human agent."
