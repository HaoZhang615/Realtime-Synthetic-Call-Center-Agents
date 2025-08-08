"""
Common utilities for multi-agent VoiceBot applications.
This module contains shared functions for agent creation, management, and orchestration
used across different multi-agent implementations.
"""

import os
import logging
from typing import Optional, Dict, Any

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

logger = logging.getLogger(__name__)


def find_existing_agent_by_name(client, name: str):
    """
    Find an existing agent by name.
    
    Args:
        client: Azure AI client (project_client or azure_ai_agent_client)
        name: Name of the agent to find
        
    Returns:
        Agent object if found, None otherwise
    """
    try:
        agents = client.agents.list_agents(limit=100)
        
        # Handle both sync and async iterators
        if hasattr(agents, '__aiter__'):
            # Async iterator (for Semantic Kernel clients)
            return None  # This should be handled in async context
        else:
            # Sync iterator (for regular AI Projects clients)
            for agent in agents:
                if agent.name == name:
                    logger.info(f"Found existing agent '{name}' with ID: {agent.id}")
                    return agent
        
        logger.info(f"No existing agent found with name: {name}")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for existing agent '{name}': {e}")
        return None


async def find_existing_agent_by_name_async(client, name: str):
    """
    Find an existing agent by name (async version for Semantic Kernel).
    
    Args:
        client: Azure AI agent client (async)
        name: Name of the agent to find
        
    Returns:
        Agent object if found, None otherwise
    """
    try:
        agents = client.agents.list_agents(limit=100)
        async for agent in agents:
            if agent.name == name:
                logger.info(f"Found existing agent '{name}' with ID: {agent.id}")
                return agent
        
        logger.info(f"No existing agent found with name: {name}")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for existing agent '{name}': {e}")
        return None


def initialize_ai_project_client() -> AIProjectClient:
    """
    Initialize Azure AI Project client with proper configuration.
    
    Returns:
        AIProjectClient: Configured project client
    """
    try:
        project_endpoint = os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"]
        
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        logger.info("Azure AI Project client initialized successfully")
        return project_client
        
    except Exception as e:
        logger.error(f"Failed to initialize AI Project client: {e}")
        raise


def get_environment_variables() -> Dict[str, Any]:
    """
    Get common environment variables used in agent configurations.
    
    Returns:
        Dict[str, Any]: Dictionary of environment variables
    """
    env_vars = {
        # Azure AI configuration
        "model_deployment": os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"),
        "project_endpoint": os.environ.get("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"),
        
        # Connection names
        "bing_connection_name": os.environ.get("BING_CUSTOM_GROUNDING_CONNECTION_NAME"),
        "ai_search_connection_name": os.environ.get("AZURE_AI_SEARCH_CONNECTION_NAME"),
        "ai_search_index": os.environ.get("AZURE_AI_SEARCH_INDEX"),
        
        # Logic App configuration
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "resource_group": os.environ.get("AZURE_RESOURCE_GROUP"),
        "logic_app_name": os.environ.get("SEND_EMAIL_LOGIC_APP_NAME"),
        "logic_app_trigger": os.environ.get("SEND_EMAIL_LOGIC_APP_TRIGGER_NAME", "When_a_HTTP_request_is_received"),
        "logic_app_url": os.environ.get("SEND_EMAIL_LOGIC_APP_URL"),
    }
    
    # Log missing critical environment variables
    critical_vars = ["model_deployment", "project_endpoint"]
    for var in critical_vars:
        if not env_vars[var]:
            logger.warning(f"Critical environment variable {var} is not set")
    
    return env_vars


def get_agent_instructions() -> Dict[str, str]:
    """
    Get standard agent instructions for different agent types.
    
    Returns:
        Dict[str, str]: Dictionary of agent instructions by agent type
    """
    return {
        "triage": """You are a sophisticated triage agent that routes user requests to specialized agents. You have access to multiple specialized agents and should delegate tasks appropriately:

1. **Web Search Agent**: Use for current news, general web information, or real-time data
2. **Knowledge Base Agent**: Use for internal company information, policies, or documented procedures  
3. **Email Agent**: Use for sending emails with specific recipients, subjects, and content

Always:
- Analyze the user's request carefully
- Choose the most appropriate specialized agent
- Provide clear, helpful responses
- Escalate complex multi-step tasks appropriately
- Maintain a professional, friendly tone""",

        "web_search": """Your job is to do web search upon user query and summarize the retrieved knowledge in your response. You will do nothing else but searching the web. Always provide relevant, up-to-date information and include source references when possible.""",

        "knowledge_base": """Your job is to search the internal knowledge base (Azure AI Search Index) and return the summarized search result back to the user. Focus on providing accurate information from company documents, policies, and procedures.""",

        "email": """You are a specialized agent for sending emails. When asked to send an email:
- Always ask for recipient email address if not provided
- Craft professional and appropriate email content
- Include current date/time when relevant
- Confirm email details before sending
- Provide clear confirmation after successful sending""",

        "concierge": """You are a sophisticated AI assistant with access to specialized agents. You can help users with various tasks including:

1. **Web Search**: Search the internet for current information and news
2. **Internal Knowledge Base**: Search internal company documents and knowledge
3. **Send Emails**: Send emails to specified recipients with custom subject and body content

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
- Maintain a friendly, engaging tone"""
    }


def cleanup_agent_resources(session_state_key: str = "connected_agents"):
    """
    Cleanup agent resources (placeholder for future cleanup logic).
    
    Args:
        session_state_key: Key in session state containing agent references
    """
    try:
        # Note: Cleanup is currently commented out to preserve agents across sessions
        # This function serves as a placeholder for future cleanup implementation
        logger.info("Agent resources cleanup completed (preserved across sessions)")
        
    except Exception as e:
        logger.error(f"Error during agent cleanup: {e}")


def validate_agent_configuration() -> bool:
    """
    Validate that required environment variables for agent configuration are present.
    
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    required_vars = [
        "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    logger.info("Agent configuration validation passed")
    return True


def log_agent_creation(agent_name: str, agent_id: str, is_new: bool = True):
    """
    Log agent creation or reuse with consistent formatting.
    
    Args:
        agent_name: Name of the agent
        agent_id: ID of the agent
        is_new: Whether this is a newly created agent or reused existing one
    """
    action = "Created new" if is_new else "Reusing existing"
    logger.info(f"{action} {agent_name}, ID: {agent_id}")
