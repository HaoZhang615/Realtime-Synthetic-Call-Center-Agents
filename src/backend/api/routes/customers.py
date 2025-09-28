"""
Customer API routes for retrieving customer data from CosmosDB
"""

import logging
import os
from typing import List, Dict
from fastapi import APIRouter, HTTPException
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
from load_azd_env import load_azd_environment

# Load environment
load_azd_environment()

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Cosmos DB client
try:
    credential = DefaultAzureCredential()
    cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
    cosmos_database = os.getenv("COSMOSDB_DATABASE")
    
    if not cosmos_endpoint or not cosmos_database:
        logger.warning("Cosmos DB configuration missing")
        cosmos_client = None
    else:
        cosmos_client = CosmosClient(cosmos_endpoint, credential)
        database = cosmos_client.get_database_client(cosmos_database)
        customer_container = database.get_container_client("Customer")
except Exception as e:
    logger.error(f"Failed to initialize Cosmos DB client: {e}")
    cosmos_client = None
    database = None
    customer_container = None


@router.get("/customers")
async def get_customers():
    """Get all customers from CosmosDB for selection in the voice interface"""
    if not customer_container:
        raise HTTPException(status_code=500, detail="Cosmos DB not configured")
    
    try:
        # Query all customers
        query = "SELECT c.customer_id, c.first_name, c.last_name FROM c"
        items = list(customer_container.query_items(
            query=query, 
            enable_cross_partition_query=True
        ))
        
        customers = [{
            'id': item['customer_id'],
            'name': f"{item['first_name']} {item['last_name']}",
            'first_name': item['first_name'],
            'last_name': item['last_name']
        } for item in items]
        
        logger.info(f"Retrieved {len(customers)} customers")
        return {"customers": customers}
        
    except exceptions.CosmosHttpResponseError as e:
        logger.error(f"CosmosDB query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query customers: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving customers: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customers")


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    """Get specific customer details"""
    if not customer_container:
        raise HTTPException(status_code=500, detail="Cosmos DB not configured")
    
    try:
        query = """SELECT c.customer_id, c.first_name, c.last_name, c.email, 
                   c.address, c.phone_number FROM c WHERE c.customer_id = @customer_id"""
        
        items = list(customer_container.query_items(
            query=query,
            parameters=[{"name": "@customer_id", "value": customer_id}],
            enable_cross_partition_query=True
        ))
        
        if not items:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
            
        return {"customer": items[0]}
        
    except HTTPException:
        raise
    except exceptions.CosmosHttpResponseError as e:
        logger.error(f"CosmosDB query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query customer: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer")