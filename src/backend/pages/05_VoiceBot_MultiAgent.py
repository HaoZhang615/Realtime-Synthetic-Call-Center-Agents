"""
Multi-Agent Voice Bot using Azure AI Agents with Connected Agent tools.
This page demonstrates how to use Azure AI Agents service with connected agents
for more sophisticated conversational AI interactions.
"""

import os
import sys
import logging
import streamlit as st
import re
import atexit
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import common utilities
from utils import (
    setup_logging_and_monitoring, initialize_azure_clients, get_session_id,
    get_customer_id, initialize_conversation, save_conversation_message,
    speech_to_text, text_to_speech, setup_sidebar_voice_controls,
    setup_sidebar_conversation_info, cleanup_response_for_tts,
    setup_page_header, setup_sidebar_header, setup_voice_input_recorder,
    setup_system_message_input, create_chat_container, handle_audio_recording,
    initialize_session_messages, add_message_to_session, handle_chat_flow,
    find_existing_agent_by_name, initialize_ai_project_client,
    get_environment_variables, get_agent_instructions, cleanup_agent_resources,
    validate_agent_configuration, log_agent_creation, display_all_messages
)

# Azure AI Agents specific imports
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ConnectedAgentTool, MessageRole, BingGroundingTool, AzureAISearchQueryType, AzureAISearchTool, ListSortOrder, ToolSet, FunctionTool

# Import AzureLogicAppTool and the function factory from utils
from utils.user_logic_apps import AzureLogicAppTool, create_send_email_function

# Configure logging and monitoring
setup_logging_and_monitoring()

logger = logging.getLogger(__name__)
logger.debug("Starting Multi-Agent VoiceBot page")

# Initialize Azure clients
client, token_provider, conversation_manager = initialize_azure_clients()

# Initialize Azure AI Project client
project_client = initialize_ai_project_client()

# Get environment variables
env_vars = get_environment_variables()
model_deployment = env_vars["model_deployment"]

def create_connected_agents():
    """Create and initialize connected agents."""
    if "connected_agents" not in st.session_state:
        try:
            # Get agent instructions
            instructions = get_agent_instructions()
            
        #----------reuse or create web search agent --------------------------------#
            # prepare Bing Grounding tool
            bing_connection_name = env_vars["bing_connection_name"]
            bing_connection_id = project_client.connections.get(name=bing_connection_name).id
            bing_conn_id = bing_connection_id
            bing = BingGroundingTool(connection_id=bing_conn_id)

            # Check for existing web search agent or create new one
            existing_web_search_agent = find_existing_agent_by_name(project_client, "WebSearchAgent")

            if not existing_web_search_agent:
                # Create web search agent using project client
                web_search_agent = project_client.agents.create_agent(
                    model=model_deployment,
                    name="WebSearchAgent",
                    instructions=instructions["web_search"],
                    tools=bing.definitions,
                )
                log_agent_creation("WebSearchAgent", web_search_agent.id, True)
            else:
                web_search_agent = existing_web_search_agent
                log_agent_creation("WebSearchAgent", web_search_agent.id, False)
            
            # Initialize Connected Agent tool
            connected_web_search_agent = ConnectedAgentTool(
                id=web_search_agent.id,
                name="web_search_agent",
                description="Gets web search results for a query"
            )
            
        #----------reuse or create AI search agent --------------------------------#
            # prepare AI Search tool
            ai_search_connection_name = env_vars["ai_search_connection_name"]
            ai_search_connection_id = project_client.connections.get(name=ai_search_connection_name).id
            ai_search_conn_id = ai_search_connection_id
            ai_search = AzureAISearchTool(
                index_connection_id=ai_search_conn_id,
                index_name=env_vars["ai_search_index"],
                query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                top_k=3,
                filter="",
            )
            
            existing_ai_search_agent = find_existing_agent_by_name(project_client, "AISearchAgent")

            if not existing_ai_search_agent:
                # Create AI search agent using project client
                ai_search_agent = project_client.agents.create_agent(
                    model=model_deployment,
                    name="AISearchAgent",
                    instructions=instructions["knowledge_base"],
                    tools=ai_search.definitions,
                    tool_resources=ai_search.resources,
                )
                log_agent_creation("AISearchAgent", ai_search_agent.id, True)
            else:
                ai_search_agent = existing_ai_search_agent
                log_agent_creation("AISearchAgent", ai_search_agent.id, False)

            # Initialize Connected Agent tool
            connected_ai_search_agent = ConnectedAgentTool(
                id=ai_search_agent.id,
                name="ai_search_agent",
                description="Gets the internal knowledge base search results for a query"
            )
            
        #----------reuse or create email agent --------------------------------#
        # email_agent = None
        # connected_email_agent = None
        # 
        # # Only create email agent if Logic App configuration is available
        # if env_vars["subscription_id"] and env_vars["resource_group"] and env_vars["logic_app_name"]:
        #     try:
        #         # Create AzureLogicAppTool instance
        #         logic_app_tool = AzureLogicAppTool(
        #             env_vars["subscription_id"], 
        #             env_vars["resource_group"], 
        #             DefaultAzureCredential()
        #         )
        #         
        #         # Register the Logic App
        #         logic_app_tool.register_logic_app(env_vars["logic_app_name"], env_vars["logic_app_trigger"])
        #         logger.info("Logic App registered successfully!")
        #         
        #         # Create the send email function
        #         send_email_func = create_send_email_function(logic_app_tool, env_vars["logic_app_name"])
        #         
        #         # Prepare the function tools for the agent
        #         functions_to_use = {send_email_func}
        #         functions = FunctionTool(functions=functions_to_use)
        #         
        #         # Check for existing email agent or create new one
        #         existing_email_agent = find_existing_agent_by_name(project_client, "SendEmailAgent")
        #         
        #         if not existing_email_agent:
        #             # Create email agent using project client
        #             email_agent = project_client.agents.create_agent(
        #                 model=model_deployment,
        #                 name="SendEmailAgent",
        #                 instructions=instructions["email"],
        #                 tools=functions.definitions,
        #             )
        #             log_agent_creation("SendEmailAgent", email_agent.id, True)
        #         else:
        #             email_agent = existing_email_agent
        #             log_agent_creation("SendEmailAgent", email_agent.id, False)
        #         
        #         # Initialize Connected Agent tool for email
        #         connected_email_agent = ConnectedAgentTool(
        #             id=email_agent.id,
        #             name="email_agent",
        #             description="Sends emails to specified recipients with custom subject and body content"
        #         )
        #         
        #     except Exception as e:
        #         logger.error(f"Error creating email agent: {e}")
        #         email_agent = None
        #         connected_email_agent = None
        # else:
        #     logger.warning("Email agent configuration not available - Logic App environment variables missing")

        #----------reuse or create concierge agent --------------------------------#
            # Check for existing main agent or create new one
            existing_concierge_agent = find_existing_agent_by_name(project_client, "ConciergeAgent")

            if not existing_concierge_agent:
                # Build tools list based on availability
                agent_tools = connected_web_search_agent.definitions + connected_ai_search_agent.definitions
                # # Add email agent tools if available
                # if connected_email_agent:
                #     agent_tools += connected_email_agent.definitions
                #     logger.info("Email agent tools added to concierge agent")

                concierge_agent = project_client.agents.create_agent(
                    model=model_deployment,
                    name="ConciergeAgent",
                    instructions=st.session_state.system_message,
                    tools=agent_tools,
                )
                log_agent_creation("ConciergeAgent", concierge_agent.id, True)
            else:
                concierge_agent = existing_concierge_agent
                log_agent_creation("ConciergeAgent", concierge_agent.id, False)
                # Update instructions for existing agent in case they changed
                try:
                    # Build tools list based on availability
                    agent_tools = connected_web_search_agent.definitions + connected_ai_search_agent.definitions
                    # # Add email agent tools if available
                    # if connected_email_agent:
                    #     agent_tools += connected_email_agent.definitions
                    #     logger.info("Email agent tools added to existing concierge agent")
                    concierge_agent = project_client.agents.update_agent(
                        agent_id=concierge_agent.id,
                        instructions=st.session_state.system_message,
                        tools=agent_tools,
                    )
                    logger.info(f"Updated existing concierge agent instructions")
                except Exception as e:
                    logger.warning(f"Could not update agent instructions: {e}")
            
            # Always create a new thread for communication (threads are session-specific)
            thread = project_client.agents.threads.create()
            logger.info(f"Created new thread, ID: {thread.id}")
            
            # Store agents in session state
            st.session_state.connected_agents = {
                "web_search_agent": web_search_agent,
                "ai_search_agent": ai_search_agent,
                "concierge_agent": concierge_agent,
                "connected_web_search_agent": connected_web_search_agent,
                "connected_ai_search_agent": connected_ai_search_agent,
            }
            # # Add email agent to session state if available
            # if email_agent and connected_email_agent:
            #     st.session_state.connected_agents["email_agent"] = email_agent
            #     st.session_state.connected_agents["connected_email_agent"] = connected_email_agent
            #     logger.info("Email agent added to session state")
            
            st.session_state.agent_thread = thread
            
            logger.info("All agents successfully initialized and stored in session state")
            agent_ids = f"Web: {web_search_agent.id}, AI Search: {ai_search_agent.id}, Concierge: {concierge_agent.id}"
            # if email_agent:
            #     agent_ids += f", Email: {email_agent.id}"
            logger.info(f"Agent IDs - {agent_ids}")
            
        except Exception as e:
            logger.error(f"Error creating connected agents: {e}")
            st.error(f"Failed to initialize connected agents: {e}")
            return False
    
    return True

def multi_agent_chat(user_request):
    """Handle chat using multi-agent system."""
    if not create_connected_agents():
        return "Sorry, I'm having trouble connecting to my specialized agents right now."
    
    try:
        thread = st.session_state.agent_thread
        concierge_agent = st.session_state.connected_agents["concierge_agent"]
        
        # Create message in thread
        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=user_request,
        )
        logger.info(f"Created message, ID: {message.id}")
        
        # Create and process agent run
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=concierge_agent.id
        )
        logger.info(f"Run finished with status: {run.status}")
        
        if run.status == "failed":
            logger.error(f"Run failed: {run.last_error}")
            return f"Sorry, I encountered an error: {run.last_error}"
        
        # Fetch latest messages
        messages = project_client.agents.messages.list(thread_id=thread.id)
        logger.info("Retrieved messages from thread (ItemPaged object)")
        
        # Convert ItemPaged to list for easier handling
        messages_list = list(messages)
        logger.info(f"Converted to list with {len(messages_list)} messages")
        
        # Debug: Log all messages
        for i, msg in enumerate(messages_list):
            logger.info(f"Message {i}: role={msg.role}, role_type={type(msg.role)}")
            logger.info(f"Message {i}: has_text_messages={bool(msg.text_messages)}")
            if msg.text_messages:
                logger.info(f"Message {i}: text_messages_count={len(msg.text_messages)}")
        
        # Get the latest assistant response
        assistant_response = None
        try:
            for msg in messages_list:
                logger.info(f"Processing message with role: {msg.role}")
                if msg.text_messages:
                    logger.info(f"Message has {len(msg.text_messages)} text messages")
                    if msg.role == MessageRole.AGENT:
                        logger.info("Found agent message, extracting response")
                        last_text = msg.text_messages[-1]
                        logger.info(f"Last text object: {type(last_text)}")
                        assistant_response = last_text.text.value
                        logger.info(f"Extracted response: {assistant_response[:100]}...")
                        break
                else:
                    logger.info("Message has no text_messages")
        except Exception as e:
            logger.error(f"Error processing messages: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
        
        if assistant_response:
            logger.info("Successfully extracted assistant response")
            # Save to Cosmos DB using common utility
            save_conversation_message(user_request, assistant_response, conversation_manager)
            return assistant_response
        else:
            logger.warning("No assistant response found")
        
        return "I'm sorry, I didn't get a response from my agents."
        
    except Exception as e:
        logger.error(f"Error in multi-agent chat: {e}")
        return f"Sorry, I encountered an error: {str(e)}"

# Streamlit UI
setup_page_header("🤖 Multi-Agent Voice Bot", "Powered by Azure AI Agents with Connected Agent tools")

# Initialize conversation
initialize_conversation(conversation_manager)

# Sidebar Configuration
setup_sidebar_header()

# Voice controls
voice_on, selected_voice, tts_instructions = setup_sidebar_voice_controls()

# System message configuration
default_system_message = """You are a sophisticated AI assistant with access to specialized agents. You can help users with various tasks including:

1. **Web Search**: Use the web_search_agent to search the internet for current information and news
2. **Internal Knowledge Base**: Use the ai_search_agent to search internal company documents and knowledge
3. **Send Emails**: Use the email_agent to send emails to specified recipients with custom subject and body content

For email tasks specifically:
- Always ask for recipient email address if not provided
- Craft professional and appropriate email content
- Include current date/time when relevant
- Confirm email details before sending

You should:
- Be professional, helpful, and concise
- Provide accurate, up-to-date information
- Ask clarifying questions if needed
- Always summarize findings clearly and provide reference links when using web search
- Use the appropriate specialized agent for each task
- Maintain a friendly, engaging tone
"""

system_message = setup_system_message_input(default_system_message)

# Conversation info
setup_sidebar_conversation_info()

# Voice input recorder
custom_audio_bytes = setup_voice_input_recorder()

# Handle audio recording
if custom_audio_bytes:
    handle_audio_recording(custom_audio_bytes, lambda audio: speech_to_text(audio, client))

# Initialize session messages
initialize_session_messages()

# Main chat interface
conversation_container = create_chat_container(600)

# Handle new messages
if text_prompt := st.chat_input("Ask me anything!"):
    prompt = text_prompt
elif "voice_prompt" in st.session_state:
    prompt = st.session_state.voice_prompt
    del st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        # Use the common chat flow handler
        def tts_func(text):
            return text_to_speech(text, client)
        
        handle_chat_flow(prompt, multi_agent_chat, voice_on, tts_func)
    else:
        # Display existing conversation
        display_all_messages()

# Cleanup on app shutdown (this runs when the script ends)
atexit.register(cleanup_agent_resources)
