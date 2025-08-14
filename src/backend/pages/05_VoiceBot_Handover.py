"""
AI-to-Human Handover Interface for Call Center Operations.
This page simulates a handover UI where human agents take over conversations from AI chatbots,
with summarized context and customer information displayed for seamless continuation.
"""

import os
import sys
import logging
import streamlit as st
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import common utilities
from utils import (
    setup_logging_and_monitoring, initialize_azure_clients, get_session_id, get_customer_id,
    setup_page_header, setup_sidebar_header, ConversationManager
)

# Azure Cosmos DB imports
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

# Configure Streamlit page to use wide layout
st.set_page_config(
    page_title="AI-to-Human Handover",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging and monitoring
setup_logging_and_monitoring()

logger = logging.getLogger(__name__)
logger.debug("Starting AI-to-Human Handover page")

# Initialize Azure clients
client, token_provider, conversation_manager = initialize_azure_clients()

class HandoverManager:
    """Manages AI-to-Human conversation handover functionality."""
    
    def __init__(self):
        """Initialize Cosmos DB clients for various containers."""
        self.setup_cosmos_clients()
        
    def setup_cosmos_clients(self):
        """Set up Cosmos DB clients for different containers."""
        try:
            # Use managed identity for secure authentication
            credential = DefaultAzureCredential()
            
            # Get Cosmos DB configuration from environment
            cosmos_endpoint = os.environ["COSMOSDB_ENDPOINT"]
            database_name = os.environ["COSMOSDB_DATABASE"]
            
            # Initialize Cosmos client and database
            self.cosmos_client = CosmosClient(cosmos_endpoint, credential)
            self.database = self.cosmos_client.get_database_client(database_name)
            
            # Initialize containers
            self.ai_conversations_container = self.database.get_container_client(
                os.environ["COSMOSDB_AIConversations_CONTAINER"]
            )
            self.human_conversations_container = self.database.get_container_client(
                os.environ["COSMOSDB_HumanConversations_CONTAINER"]
            )
            self.customer_container = self.database.get_container_client(
                os.environ["COSMOSDB_Customer_CONTAINER"]
            )
            self.vehicles_container = self.database.get_container_client(
                os.environ.get("COSMOSDB_Vehicles_CONTAINER", "Vehicles")
            )
            self.assistance_cases_container = self.database.get_container_client(
                os.environ.get("COSMOSDB_AssistanceCases_CONTAINER", "AssistanceCases")
            )
            
            logger.info("Successfully connected to all Cosmos DB containers")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB clients: {e}")
            raise

    def get_customer_info(self, customer_id: str) -> Optional[Dict]:
        """Retrieve customer information from Customer container."""
        try:
            query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
            items = list(self.customer_container.query_items(
                query=query,
                enable_cross_partition_query=True,
                max_item_count=1
            ))
            return items[0] if items else None
        except exceptions.CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error retrieving customer info: {e}")
            return None

    def get_customer_vehicles(self, customer_id: str) -> List[Dict]:
        """Retrieve customer's vehicles from Vehicles container."""
        try:
            query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
            items = list(self.vehicles_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except exceptions.CosmosResourceNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Error retrieving customer vehicles: {e}")
            return []

    def get_assistance_cases(self, customer_id: str) -> List[Dict]:
        """Retrieve customer's assistance cases from AssistanceCases container."""
        try:
            query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
            items = list(self.assistance_cases_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except exceptions.CosmosResourceNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Error retrieving assistance cases: {e}")
            return []

    def get_most_recent_ai_conversation(self, *args, **kwargs):
        """Get the most recent AI conversation for handover. If no customer_id provided, get the most recent overall."""
        # Handle both positional and keyword arguments
        customer_id = None
        if args:
            customer_id = args[0]
        elif 'customer_id' in kwargs:
            customer_id = kwargs['customer_id']
        
        try:
            if customer_id:
                # Look for specific customer's conversation
                query = """
                    SELECT * FROM c 
                    WHERE c.customer_id = @customer_id 
                    ORDER BY c.updated_at DESC 
                    OFFSET 0 LIMIT 1
                """
                parameters = [{"name": "@customer_id", "value": customer_id}]
                enable_cross_partition = False
            else:
                # Look for the most recent conversation across all customers
                query = """
                    SELECT * FROM c 
                    ORDER BY c.updated_at DESC 
                    OFFSET 0 LIMIT 1
                """
                parameters = []
                enable_cross_partition = True
            
            items = list(self.ai_conversations_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=enable_cross_partition,
                max_item_count=1
            ))
            return items[0] if items else None
        except Exception as e:
            logger.error(f"Error retrieving recent AI conversation: {e}")
            return None

    def summarize_conversation(self, messages: List[Dict]) -> str:
        """Generate a summary of the AI conversation using Azure OpenAI."""
        system_message = """You are a helpful customer service representative who is good at looking at a prior customer-agent conversation and provide a key-points based summary with the key-points being: 'Issue Reported', 'Already provided help', 'Customer expectation as next', and 'conversation language'."""
        
        prompt = "Summarize the following conversation:\n\n"
        for message in messages:
            role = message.get('role', 'unknown')
            content = message.get('content', '')
            prompt += f"{role.capitalize()}: {content}\n"
        
        try:
            completion = client.chat.completions.create(
                model=os.environ.get("AOAI_GPT4O_MINI_MODEL", "gpt-4o-mini"),
                temperature=0.0,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating conversation summary: {e}")
            return "Error generating summary. Please review the conversation manually."

    def generate_recommended_reply(self, customer_id: str, ai_conversation: Dict, json_summary: Dict = None) -> str:
        """Generate a recommended reply for the human agent using AI conversation and structured data."""
        system_message = """You are a senior customer service agent who is good at giving next-turn reply to keep an engaging conversation and solving customer's problem. You got forwarded an existing customer service conversation done by another junior agent with extra provided context of customer information and previous cases.

This is a live chat so do expect a quick response from the customer, do not reply like the customer is offline. You will initiate the conversation with the customer.

The existing conversation:

"""
        
        # Add conversation history
        if 'messages' in ai_conversation:
            for message in ai_conversation['messages']:
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                system_message += f"{role.capitalize()}: {content}\n"
        
        # Add structured summary if available
        if json_summary:
            system_message += f"\n\nStructured Summary from AI Conversation:\n"
            
            # Personal info
            personal_info = json_summary.get('personalInfo', {})
            if personal_info:
                system_message += f"Customer: {personal_info.get('firstName', '')} {personal_info.get('lastName', '')}\n"
            
            # Vehicle info
            vehicle_info = json_summary.get('vehicleInfo', {})
            if vehicle_info:
                system_message += f"Vehicle: {vehicle_info.get('brand', '')} {vehicle_info.get('model', '')} (Plate: {vehicle_info.get('plateNumber', '')})\n"
            
            # Incident info
            incident_info = json_summary.get('incidentInfo', {})
            if incident_info:
                system_message += f"Problem: {incident_info.get('causeDescription', '')}\n"
                system_message += f"Location: {incident_info.get('location', '')}\n"
                system_message += f"Urgency: {'Urgent' if incident_info.get('isItUrgent') else 'Not urgent'}\n"
                system_message += f"Passengers: {incident_info.get('NrOfAdultsInCarForTowing', 0)} adults, {incident_info.get('NrOfChildrenInCarForTowing', 0)} children\n"
        
        # Add customer information
        customer_info = self.get_customer_info(customer_id)
        if customer_info:
            customer_info_str = json.dumps(customer_info, indent=4)
            system_message += f"\nDetailed Customer Information:\n{customer_info_str}\n"
        
        # Add assistance cases
        assistance_cases = self.get_assistance_cases(customer_id)
        if assistance_cases:
            cases_str = json.dumps(assistance_cases, indent=4)
            system_message += f"\nPrevious Assistance Cases:\n{cases_str}\n"
        
        try:
            completion = client.chat.completions.create(
                model=os.environ.get("AOAI_GPT4O_MINI_MODEL", "gpt-4o-mini"),
                temperature=0.5,
                max_tokens=800,
                messages=[{"role": "system", "content": system_message}]
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating recommended reply: {e}")
            return "Welcome back! I'm taking over from our AI assistant. How can I continue to help you today?"

    def simulate_customer_response(self, agent_message: str, conversation_context: Dict, json_summary: Dict = None) -> str:
        """Generate a realistic customer response using Azure OpenAI."""
        # Build context for customer simulation
        system_message = """You are simulating a customer in a call center conversation. You are responding to a human agent who has taken over from an AI chatbot. 

Your characteristics:
- You are experiencing a real vehicle breakdown/issue
- You are seeking genuine help and assistance
- You respond naturally and conversationally
- You may ask follow-up questions or provide additional information
- You show appropriate emotions (frustration, relief, gratitude, etc.)
- You keep responses concise but natural (1-2 sentences typically)
- You respond in the same language as the conversation (German/English)

Context from your previous AI conversation:
"""
        
        # Add original AI conversation context
        if 'messages' in conversation_context:
            system_message += "\nPrevious AI conversation:\n"
            for message in conversation_context['messages'][-6:]:  # Last 6 messages for context
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                system_message += f"{role.capitalize()}: {content}\n"
        
        # Add structured context if available
        if json_summary:
            personal_info = json_summary.get('personalInfo', {})
            vehicle_info = json_summary.get('vehicleInfo', {})
            incident_info = json_summary.get('incidentInfo', {})
            
            if personal_info:
                system_message += f"\nYour name: {personal_info.get('firstName', '')} {personal_info.get('lastName', '')}\n"
            
            if vehicle_info:
                system_message += f"Your vehicle: {vehicle_info.get('brand', '')} {vehicle_info.get('model', '')} (Plate: {vehicle_info.get('plateNumber', '')})\n"
            
            if incident_info:
                system_message += f"Your problem: {incident_info.get('causeDescription', '')}\n"
                system_message += f"Location: {incident_info.get('location', '')}\n"
                urgency = "urgent" if incident_info.get('isItUrgent') else "not urgent"
                system_message += f"Situation urgency: {urgency}\n"
        
        system_message += f"\nThe human agent just said: '{agent_message}'\n\nRespond naturally as the customer:"
        
        try:
            completion = client.chat.completions.create(
                model=os.environ.get("AOAI_GPT4O_MINI_MODEL", "gpt-4o-mini"),
                temperature=0.7,  # Higher temperature for more natural variation
                max_tokens=150,   # Keep responses concise
                messages=[{"role": "system", "content": system_message}]
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating customer response: {e}")
            # Fallback responses based on context
            if json_summary and json_summary.get('incidentInfo', {}).get('isItUrgent'):
                return "Thank you for taking over. I really need help as soon as possible."
            else:
                return "Thank you for taking over. I appreciate the personalized assistance."

    def save_human_conversation(self, session_id: str, customer_id: str, messages: List[Dict]) -> bool:
        """Save human conversation to Human_Conversations container."""
        document_id = f"human_chat_{session_id}"
        
        try:
            # Try to read existing document
            try:
                item = self.human_conversations_container.read_item(
                    item=document_id, 
                    partition_key=customer_id
                )
                item['messages'] = messages
                item['updated_at'] = datetime.now(timezone.utc).isoformat()
                self.human_conversations_container.replace_item(item=item, body=item)
            except exceptions.CosmosResourceNotFoundError:
                # Create new document
                self.human_conversations_container.create_item({
                    'id': document_id,
                    'session_id': session_id,
                    'customer_id': customer_id,
                    'messages': messages,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
            return True
        except Exception as e:
            logger.error(f"Error saving human conversation: {e}")
            return False

# Initialize handover manager (force recreation to pick up method signature changes)
if 'handover_manager' not in st.session_state or 'handover_manager_version' not in st.session_state or st.session_state.get('handover_manager_version', 0) < 4:
    try:
        st.session_state.handover_manager = HandoverManager()
        st.session_state.handover_manager_version = 4  # Version flag to force refresh
        logger.info("HandoverManager initialized/refreshed successfully")
    except Exception as e:
        st.error(f"Failed to initialize HandoverManager: {e}")
        st.stop()

def display_customer_info_from_ai(personal_info: Dict, vehicle_info: Dict, incident_info: Dict, customer_info: Dict = None):
    """Display customer information extracted from AI conversation and database."""
    st.subheader("👤 Customer Information")
    
    if personal_info or customer_info:
        col1, col2 = st.columns(2)
        with col1:
            # Use AI conversation data first, fallback to database
            first_name = personal_info.get('firstName', '') or (customer_info.get('first_name', '') if customer_info else '')
            last_name = personal_info.get('lastName', '') or (customer_info.get('last_name', '') if customer_info else '')
            
            st.write(f"**Name:** {first_name} {last_name}")
            if customer_info:
                st.write(f"**Customer ID:** {customer_info.get('customer_id', 'N/A')}")
                st.write(f"**Email:** {customer_info.get('email', 'N/A')}")
                st.write(f"**Phone:** {customer_info.get('phone_number', 'N/A')}")
        with col2:
            if customer_info:
                st.write(f"**Language:** {customer_info.get('language_preference', 'N/A')}")
                st.write(f"**Member Since:** {customer_info.get('customer_since', 'N/A')}")
                st.write(f"**Membership #:** {customer_info.get('membership_number', 'N/A')}")
                if 'address' in customer_info:
                    address = customer_info['address']
                    st.write(f"**Address:** {address.get('street', '')}, {address.get('city', '')}, {address.get('canton', '')}")
    
    # Vehicle Information from AI conversation
    if vehicle_info:
        st.subheader("🚗 Vehicle in Question")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**License Plate:** {vehicle_info.get('plateNumber', 'N/A')}")
            st.write(f"**Make:** {vehicle_info.get('brand', 'N/A')}")
            st.write(f"**Model:** {vehicle_info.get('model', 'N/A')}")
        with col2:
            # Additional vehicle details can be added here if available
            pass
    
    # Incident Information from AI conversation
    if incident_info:
        st.subheader("🚨 Incident Details")
        st.write(f"**Problem Description:** {incident_info.get('causeDescription', 'N/A')}")
        st.write(f"**Location:** {incident_info.get('location', 'N/A')}")
        st.write(f"**Adults in Car:** {incident_info.get('NrOfAdultsInCarForTowing', 'N/A')}")
        st.write(f"**Children in Car:** {incident_info.get('NrOfChildrenInCarForTowing', 'N/A')}")
        st.write(f"**Urgent:** {'Yes' if incident_info.get('isItUrgent') else 'No'}")
        if incident_info.get('otherRelevantInfoForAssistance'):
            st.write(f"**Other Info:** {incident_info['otherRelevantInfoForAssistance']}")

def display_customer_info(customer_info: Dict):
    """Display customer information in a structured format."""
    if customer_info:
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Customer ID:** {customer_info.get('customer_id', 'N/A')}")
            st.write(f"**Name:** {customer_info.get('first_name', '')} {customer_info.get('last_name', '')}")
            st.write(f"**Email:** {customer_info.get('email', 'N/A')}")
            st.write(f"**Phone:** {customer_info.get('phone_number', 'N/A')}")
        with col2:
            st.write(f"**Language:** {customer_info.get('language_preference', 'N/A')}")
            st.write(f"**Member Since:** {customer_info.get('customer_since', 'N/A')}")
            st.write(f"**Membership #:** {customer_info.get('membership_number', 'N/A')}")
            if 'address' in customer_info:
                address = customer_info['address']
                st.write(f"**Address:** {address.get('street', '')}, {address.get('city', '')}, {address.get('canton', '')}")
    else:
        st.write("Customer information not found.")

def display_customer_vehicles(vehicles: List[Dict]):
    """Display customer's vehicles."""
    if vehicles:
        for i, vehicle in enumerate(vehicles):
            with st.expander(f"Vehicle {i+1}: {vehicle.get('license_plate', 'Unknown')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**License Plate:** {vehicle.get('license_plate', 'N/A')}")
                    st.write(f"**Make:** {vehicle.get('make', 'N/A')}")
                    st.write(f"**Model:** {vehicle.get('model', 'N/A')}")
                with col2:
                    st.write(f"**Year:** {vehicle.get('year', 'N/A')}")
                    st.write(f"**Color:** {vehicle.get('color', 'N/A')}")
                    st.write(f"**Registration Date:** {vehicle.get('registration_date', 'N/A')}")
    else:
        st.write("No vehicles found.")

def display_assistance_cases(cases: List[Dict]):
    """Display previous assistance cases."""
    if cases:
        for i, case in enumerate(cases):
            with st.expander(f"Case {i+1}: {case.get('case_type', 'Unknown')} - {case.get('case_date', 'Unknown Date')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Case ID:** {case.get('case_id', 'N/A')}")
                    st.write(f"**Type:** {case.get('case_type', 'N/A')}")
                    st.write(f"**Status:** {case.get('status', 'N/A')}")
                with col2:
                    st.write(f"**Date:** {case.get('case_date', 'N/A')}")
                    st.write(f"**Location:** {case.get('location', 'N/A')}")
                    if 'description' in case:
                        st.write(f"**Description:** {case['description']}")
    else:
        st.write("No previous assistance cases found.")

# Streamlit UI
setup_page_header("🤝 AI-to-Human Handover", "Seamless conversation transition from AI to human agents")

# Sidebar Configuration
setup_sidebar_header()

# Session state initialization
if "human_conversation_messages" not in st.session_state:
    st.session_state.human_conversation_messages = []
    st.session_state.handover_session_id = str(uuid.uuid4())

# Get the most recent AI conversation document directly
try:
    ai_conversation = st.session_state.handover_manager.get_most_recent_ai_conversation()
    if ai_conversation and 'customer_id' in ai_conversation:
        customer_id = ai_conversation['customer_id']
        logger.info(f"Using customer_id from recent AI conversation: {customer_id}")
        
        # Extract structured information from JSON_Summary if available
        json_summary = ai_conversation.get('JSON_Summary', {})
        personal_info = json_summary.get('personalInfo', {})
        vehicle_info = json_summary.get('vehicleInfo', {})
        incident_info = json_summary.get('incidentInfo', {})
        
    else:
        # Fallback to current session customer_id
        customer_id = get_customer_id()
        ai_conversation = None
        json_summary = {}
        personal_info = {}
        vehicle_info = {}
        incident_info = {}
        logger.info(f"No recent AI conversation found, using session customer_id: {customer_id}")
        
except Exception as e:
    st.error(f"Error getting AI conversation: {e}")
    customer_id = get_customer_id()
    ai_conversation = None
    json_summary = {}
    personal_info = {}
    vehicle_info = {}
    incident_info = {}
    logger.error(f"Fallback to session customer_id: {customer_id}, Error: {e}")

# Main layout - Adjusted for wider screen utilization
left_col, right_col = st.columns([1.2, 1])

# Left column - Customer information and context
with left_col:
       
    # Show data retrieval status
    customer_info = st.session_state.handover_manager.get_customer_info(customer_id)
    vehicles = st.session_state.handover_manager.get_customer_vehicles(customer_id)
    assistance_cases = st.session_state.handover_manager.get_assistance_cases(customer_id)
    
    # Display customer info using AI conversation data + database data
    display_customer_info_from_ai(personal_info, vehicle_info, incident_info, customer_info)
    
    # Show all customer vehicles from database if available
    if vehicles:
        st.subheader("🚗 All Customer Vehicles")
        display_customer_vehicles(vehicles)
    
    # Show previous assistance cases
    if assistance_cases:
        st.subheader("📋 Previous Assistance Cases")
        display_assistance_cases(assistance_cases)
    
    # AI-generated recommended reply
    st.subheader("🤖 Recommended Reply")
    
    # Initialize or get cached recommended reply
    if "cached_recommended_reply" not in st.session_state:
        if ai_conversation:
            try:
                st.session_state.cached_recommended_reply = st.session_state.handover_manager.generate_recommended_reply(
                    customer_id, ai_conversation, json_summary
                )
            except Exception as e:
                st.error(f"Error generating recommended reply: {e}")
                st.session_state.cached_recommended_reply = "Hello! I'm taking over from our AI assistant to help with your case. How can I continue to assist you today?"
        else:
            st.session_state.cached_recommended_reply = "Hello! I'm here to assist you. How can I help you today?"
    
    # Refresh button
    col1, col2 = st.columns([3, 1])
    with col2:
        refresh_reply_button = st.button("🔄 Refresh", help="Generate new recommended reply based on current conversation")
    
    # Handle refresh button click
    if refresh_reply_button:
        # Create updated context including human conversation messages
        updated_context = ai_conversation.copy() if ai_conversation else {"messages": []}
        
        # Add human conversation messages to context if any
        if st.session_state.human_conversation_messages:
            # Add a separator to distinguish AI conversation from human conversation
            updated_context["messages"] = updated_context.get("messages", []) + [
                {"role": "system", "content": "--- Handover to Human Agent ---", "timestamp": ""}
            ] + st.session_state.human_conversation_messages
        
        try:
            st.session_state.cached_recommended_reply = st.session_state.handover_manager.generate_recommended_reply(
                customer_id, updated_context, json_summary
            )
            st.success("Recommended reply refreshed!")
        except Exception as e:
            st.error(f"Error refreshing recommended reply: {e}")
    
    # Text area for editing the recommended reply
    recommended_reply_box = st.text_area(
        "Edit and use the suggested response:",
        value=st.session_state.cached_recommended_reply,
        height=150,
        label_visibility="collapsed"
    )
    
    # Button to use the recommended reply
    use_reply_button = st.button("Use This Reply", type="primary")

# Right column - Conversation summary and live chat
with right_col:
    st.subheader("📄 Summary of Prior AI Conversation")
    
    if ai_conversation and 'messages' in ai_conversation:
        summary = st.session_state.handover_manager.summarize_conversation(ai_conversation['messages'])
        st.write(summary)
        
        # Show original conversation in an expander
        with st.expander("View Original AI Conversation"):
            for msg in ai_conversation['messages']:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', '')
                st.write(f"**{role.capitalize()}** ({timestamp}): {content}")
    else:
        st.write("No prior AI conversation found for this customer.")
    
    st.subheader("💬 Live Human Chat")
    
    # Control buttons
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        save_chat_button = st.button("Save Chat")
    with col3:
        new_chat_button = st.button("New Chat")
    
    if new_chat_button:
        st.session_state.human_conversation_messages = []
        st.session_state.handover_session_id = str(uuid.uuid4())
        st.rerun()
    
    # Chat container - Increased height for wider screen
    chat_container = st.container(height=600, border=True)
    
    # Handle new messages
    prompt = None
    if text_prompt := st.chat_input("Type your response here..."):
        prompt = text_prompt
    elif use_reply_button and recommended_reply_box:
        prompt = recommended_reply_box
    
    # Process new message
    if prompt:
        # Add user (agent) message
        st.session_state.human_conversation_messages.append({
            "role": "agent",
            "content": prompt,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Generate realistic customer response using AI
        with st.spinner("Customer is typing..."):
            try:
                customer_response = st.session_state.handover_manager.simulate_customer_response(
                    prompt, ai_conversation or {"messages": []}, json_summary
                )
            except Exception as e:
                st.error(f"Error generating customer response: {e}")
                # Fallback to simple response
                customer_response = "Thank you for taking over. I appreciate the help."
        
        st.session_state.human_conversation_messages.append({
            "role": "customer", 
            "content": customer_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Save conversation
        st.session_state.handover_manager.save_human_conversation(
            st.session_state.handover_session_id,
            customer_id,
            st.session_state.human_conversation_messages
        )
    
    # Display conversation
    with chat_container:
        for message in st.session_state.human_conversation_messages:
            role = message["role"]
            content = message["content"]
            
            # Use appropriate avatar and styling
            if role == "agent":
                with st.chat_message("assistant", avatar="👨‍💼"):
                    st.markdown(content)
            else:  # customer
                with st.chat_message("user", avatar="👤"):
                    st.markdown(content)
    
    # Save chat functionality
    if save_chat_button:
        success = st.session_state.handover_manager.save_human_conversation(
            st.session_state.handover_session_id,
            customer_id,
            st.session_state.human_conversation_messages
        )
        if success:
            st.success("Chat saved successfully!")
        else:
            st.error("Failed to save chat.")

# Footer with information
st.markdown("---")