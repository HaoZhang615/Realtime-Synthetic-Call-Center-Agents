"""
Multi-Agent Voice Bot using Azure AI Agents with Connected Agent tools.
This page demonstrates how to use Azure AI Agents service with connected agents
for more sophisticated conversational AI interactions.
"""

import os
import sys
import logging
import hashlib
import streamlit as st
import io
import re
import atexit
import requests
from datetime import datetime
import pytz

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.agents import AgentsClient
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ConnectedAgentTool, MessageRole, BingGroundingTool, AzureAISearchQueryType, AzureAISearchTool, ListSortOrder, ToolSet, FunctionTool
from audio_recorder_streamlit import audio_recorder
from azure.monitor.opentelemetry import configure_azure_monitor

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from utils import load_dotenv_from_azd
from utils.conversation_manager import ConversationManager

# Import AzureLogicAppTool and the function factory from utils
from utils.user_logic_apps import AzureLogicAppTool, create_send_email_function

# Configure logging
logging.captureWarnings(True)
logging.basicConfig(level=logging.DEBUG)  # Changed to DEBUG for better visibility
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())

if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

logger = logging.getLogger(__name__)
logger.debug("Starting Multi-Agent VoiceBot page")

# Load environment variables from azd
load_dotenv_from_azd()

# Azure credentials and token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

# Azure OpenAI Configuration
api_base = os.environ["AZURE_OPENAI_ENDPOINT"]
api_version = "2025-03-01-preview"
gpt4omini = os.environ["AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT"]

# Audio model configurations
transcribe_model = os.environ.get("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "gpt-4o-mini-transcribe")
tts_model = os.environ.get("AZURE_OPENAI_TTS_DEPLOYMENT", "gpt-4o-mini-tts")

# Azure AI Agents Configuration
project_endpoint = os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"]
model_deployment = os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"]
bing_connection_name = os.environ["BING_GROUNDING_CONNECTION_NAME"]

# Logic App Configuration for SendEmail agent
send_email_logic_app_url = os.environ.get("SEND_EMAIL_LOGIC_APP_URL")

# Initialize clients
client = AzureOpenAI(
    azure_endpoint=api_base,
    azure_ad_token_provider=token_provider,
    api_version=api_version
)

# Initialize Azure AI Agents clients
project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),
)

# Initialize conversation manager
try:
    conversation_manager = ConversationManager()
    logger.info("Conversation manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize conversation manager: {e}")
    conversation_manager = None

def get_session_id():
    """Generate a unique session ID for the current Streamlit session."""
    if "session_id" not in st.session_state:
        session_data = str(st.session_state)
        st.session_state.session_id = hashlib.md5(session_data.encode()).hexdigest()[:16]
    return st.session_state.session_id

def get_customer_id():
    """Generate or get customer ID for conversation partitioning."""
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = f"demo_user_{get_session_id()}"
    return st.session_state.customer_id

def initialize_conversation():
    """Initialize or load conversation from Cosmos DB."""
    if "conversation_doc" not in st.session_state and conversation_manager:
        customer_id = get_customer_id()
        session_id = get_session_id()
        
        st.session_state.conversation_doc = conversation_manager.create_conversation_document(
            customer_id=customer_id,
            session_id=session_id
        )
        
        logger.info(f"Initialized new conversation: {st.session_state.conversation_doc['id']}")

def save_conversation_to_cosmos():
    """Save current conversation to Cosmos DB."""
    if conversation_manager and "conversation_doc" in st.session_state:
        success = conversation_manager.save_conversation(st.session_state.conversation_doc)
        if success:
            logger.debug("Conversation saved to Cosmos DB")
        else:
            logger.error("Failed to save conversation to Cosmos DB")

def find_existing_agent_by_name(client, name):
    """Find an existing agent by name."""
    try:
        agents = client.agents.list_agents(limit=100)
        for agent in agents:
            if agent.name == name:
                logger.info(f"Found existing agent '{name}' with ID: {agent.id}")
                return agent
        logger.info(f"No existing agent found with name: {name}")
        return None
    except Exception as e:
        logger.error(f"Error searching for existing agent '{name}': {e}")
        return None

def create_connected_agents():
    """Create and initialize connected agents."""
    if "connected_agents" not in st.session_state:
        try:
        #----------reuse or create web search agent --------------------------------#
            # prepare Bing Grounding tool
            bing_connection_name = os.environ["BING_GROUNDING_CONNECTION_NAME"]
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
                    instructions="Your job is to do web search upon user query and summarize the retrieved knowledge in your response. You will do nothing else but searching the web.",
                    tools=bing.definitions,
                )
                logger.info(f"Created new web search agent, ID: {web_search_agent.id}")
            else:
                web_search_agent = existing_web_search_agent
                logger.info(f"Reusing existing web search agent, ID: {web_search_agent.id}")
            # Initialize Connected Agent tool
            connected_web_search_agent = ConnectedAgentTool(
                id=web_search_agent.id,
                name="web_search_agent",
                description="Gets web search results for a query"
            )
        #----------reuse or create AI search agent --------------------------------#
            # prepare AI Search tool
            ai_search_connection_name = os.environ["AZURE_AI_SEARCH_CONNECTION_NAME"] 
            ai_search_connection_id = project_client.connections.get(name=ai_search_connection_name).id
            ai_search_conn_id = ai_search_connection_id
            ai_search = AzureAISearchTool(
                index_connection_id=ai_search_conn_id,
                index_name=os.environ["AZURE_AI_SEARCH_INDEX"],  # Name of the search index
                query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,  # Query type (e.g., SIMPLE, FULL)
                top_k=3,  # Number of top results to retrieve
                filter="",  # Optional filter for search results
            )
            
            existing_ai_search_agent = find_existing_agent_by_name(project_client, "AISearchAgent")

            if not existing_ai_search_agent:
                # Create AI search agent using project client
                ai_search_agent = project_client.agents.create_agent(
                    model=model_deployment,
                    name="AISearchAgent",
                    instructions="Your job is to search the internal knowledge base (a Azure AI Search Index) and return the summarized search result back to the user. ",
                    tools=ai_search.definitions,
                    tool_resources=ai_search.resources,
                )
                logger.info(f"Created new AI search agent, ID: {ai_search_agent.id}")
            else:
                ai_search_agent = existing_ai_search_agent
                logger.info(f"Reusing existing AI search agent, ID: {ai_search_agent.id}")

            # Initialize Connected Agent tool
            connected_ai_search_agent = ConnectedAgentTool(
                id=ai_search_agent.id,
                name="ai_search_agent",
                description="Gets the internal knowledge base search results for a query"
            )
        #----------reuse or create email agent --------------------------------#
            # Create AzureLogicAppTool instance for email functionality
            subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
            resource_group = os.environ.get("AZURE_RESOURCE_GROUP")
            logic_app_name = os.environ.get("SEND_EMAIL_LOGIC_APP_NAME")
            trigger_name = os.environ.get("SEND_EMAIL_LOGIC_APP_TRIGGER_NAME", "When_a_HTTP_request_is_received")
            
            email_agent = None
            connected_email_agent = None
            
            # Only create email agent if Logic App configuration is available
            if subscription_id and resource_group and logic_app_name:
                try:
                    # Create AzureLogicAppTool instance
                    logic_app_tool = AzureLogicAppTool(subscription_id, resource_group, DefaultAzureCredential())
                    
                    # Register the Logic App
                    logic_app_tool.register_logic_app(logic_app_name, trigger_name)
                    logger.info("Logic App registered successfully!")
                    
                    # Create the send email function
                    send_email_func = create_send_email_function(logic_app_tool, logic_app_name)
                    
                    # Prepare the function tools for the agent
                    functions_to_use = {send_email_func}
                    functions = FunctionTool(functions=functions_to_use)
                    
                    # Check for existing email agent or create new one
                    existing_email_agent = find_existing_agent_by_name(project_client, "SendEmailAgent")
                    
                    if not existing_email_agent:
                        # Create email agent using project client
                        email_agent = project_client.agents.create_agent(
                            model=model_deployment,
                            name="SendEmailAgent",
                            instructions="You are a specialized agent for sending emails. When asked to send an email, always ask for recipient email address if not provided, craft professional and appropriate email content, include current date/time when relevant, and confirm email details before sending.",
                            tools=functions.definitions,
                        )
                        logger.info(f"Created new email agent, ID: {email_agent.id}")
                    else:
                        email_agent = existing_email_agent
                        logger.info(f"Reusing existing email agent, ID: {email_agent.id}")
                    
                    # Initialize Connected Agent tool for email
                    connected_email_agent = ConnectedAgentTool(
                        id=email_agent.id,
                        name="email_agent",
                        description="Sends emails to specified recipients with custom subject and body content"
                    )
                    
                except Exception as e:
                    logger.error(f"Error creating email agent: {e}")
                    email_agent = None
                    connected_email_agent = None
            else:
                logger.warning("Email agent configuration not available - Logic App environment variables missing")

        #----------reuse or create concierge agent --------------------------------#
            # Check for existing main agent or create new one
            existing_concierge_agent = find_existing_agent_by_name(project_client, "ConciergeAgent")

            if not existing_concierge_agent:
                # Create concierge agent with connected agent tool using project_client
                # Initialize Connected Agent tools for both agents
                
                # Build tools list based on availability
                agent_tools = connected_web_search_agent.definitions + connected_ai_search_agent.definitions
                
                # Add email agent tools if available
                if connected_email_agent:
                    agent_tools += connected_email_agent.definitions
                    logger.info("Email agent tools added to concierge agent")

                concierge_agent = project_client.agents.create_agent(
                    model=model_deployment,
                    name="ConciergeAgent",
                    instructions=st.session_state.system_message,
                    tools=agent_tools,
                )
                logger.info(f"Created new concierge agent, ID: {concierge_agent.id}")
            else:
                concierge_agent = existing_concierge_agent
                logger.info(f"Reusing existing concierge agent, ID: {concierge_agent.id}")
                # Update instructions for existing agent in case they changed
                try:
                    # Build tools list based on availability
                    agent_tools = connected_web_search_agent.definitions + connected_ai_search_agent.definitions
                    
                    # Add email agent tools if available
                    if connected_email_agent:
                        agent_tools += connected_email_agent.definitions
                        logger.info("Email agent tools added to existing concierge agent")
                        
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
            
            # Add email agent to session state if available
            if email_agent and connected_email_agent:
                st.session_state.connected_agents["email_agent"] = email_agent
                st.session_state.connected_agents["connected_email_agent"] = connected_email_agent
                logger.info("Email agent added to session state")
            
            st.session_state.agent_thread = thread
            
            logger.info("All agents successfully initialized and stored in session state")
            agent_ids = f"Web: {web_search_agent.id}, AI Search: {ai_search_agent.id}, Concierge: {concierge_agent.id}"
            if email_agent:
                agent_ids += f", Email: {email_agent.id}"
            logger.info(f"Agent IDs - {agent_ids}")
            
        except Exception as e:
            logger.error(f"Error creating connected agents: {e}")
            st.error(f"Failed to initialize connected agents: {e}")
            return False
    
    return True

def cleanup_agents():
    """Cleanup agents when done."""
    if "connected_agents" in st.session_state:
        try:
            agents = st.session_state.connected_agents
            # Note: Cleanup commented out to preserve agents across sessions
            # Uncomment if you want to delete agents after each session
            # project_client.agents.delete_agent(agents["concierge_agent"].id)
            # project_client.agents.delete_agent(agents["web_search_agent"].id)
            # project_client.agents.delete_agent(agents["ai_search_agent"].id)
            # if "email_agent" in agents:
            #     project_client.agents.delete_agent(agents["email_agent"].id)
            logger.info("Agents cleanup completed")
        except Exception as e:
            logger.error(f"Error during agent cleanup: {e}")

def speech_to_text(audio: bytes) -> str:
    """Convert speech to text using Azure OpenAI."""
    buffer = io.BytesIO(audio)
    buffer.name = "audio.wav"
    transcription_result = client.audio.transcriptions.create(
        file=buffer,
        model=transcribe_model,
        response_format="json"
    )
    buffer.close()
    return transcription_result.text

def text_to_speech(text_input: str):
    """Convert text to speech using Azure OpenAI."""
    response = client.audio.speech.create(
        model=tts_model,
        voice=st.session_state.selected_voice,
        input=text_input,
        response_format="wav",
        instructions=st.session_state.tts_instructions
    )
    return response.content

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
        
        # Get the latest assistant response (following the working pattern from 06_connected_agents.py)
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
            # Save to Cosmos DB if available
            if conversation_manager and "conversation_doc" in st.session_state:
                try:
                    conversation_manager.add_message_to_conversation(
                        st.session_state.conversation_doc,
                        role="user",
                        content=user_request
                    )
                    conversation_manager.add_message_to_conversation(
                        st.session_state.conversation_doc,
                        role="assistant",
                        content=assistant_response
                    )
                    save_conversation_to_cosmos()
                except Exception as e:
                    logger.error(f"Error saving conversation to Cosmos DB: {e}")
            
            return assistant_response
        else:
            logger.warning("No assistant response found")
        
        return "I'm sorry, I didn't get a response from my agents."
        
    except Exception as e:
        logger.error(f"Error in multi-agent chat: {e}")
        return f"Sorry, I encountered an error: {str(e)}"

# Streamlit UI
st.title("🤖 Multi-Agent Voice Bot")
st.markdown("*Powered by Azure AI Agents with Connected Agent tools*")

# Initialize conversation
initialize_conversation()

# Sidebar Configuration
with st.sidebar:
    st.header("🎛️ Configuration")
    
    # Voice settings
    if "voice_on" not in st.session_state:
        st.session_state.voice_on = False
    st.session_state.voice_on = st.toggle(label="🔊 Enable Voice Output", value=st.session_state.voice_on)
    
    available_voices = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
    if "selected_voice" not in st.session_state:
        st.session_state.selected_voice = "shimmer"
    st.session_state.selected_voice = st.selectbox(
        "🎤 Select Voice:",
        available_voices,
        index=available_voices.index(st.session_state.selected_voice)
    )
    
    if "tts_instructions" not in st.session_state:
        st.session_state.tts_instructions = "Speak with a professional, helpful tone."
    st.session_state.tts_instructions = st.text_input(
        "🗣️ Voice Instructions:",
        value=st.session_state.tts_instructions,
        placeholder="Enter voice customization instructions...",
        help="Customize how the AI should speak"
    )
    
    # System message configuration
    if "system_message" not in st.session_state:
        st.session_state.system_message = """You are a sophisticated AI assistant with access to specialized agents. You can help users with various tasks including:

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

    st.session_state.system_message = st.text_area(
        "🧠 System Instructions:",
        value=st.session_state.system_message,
        height=150,
        help="Define the AI assistant's behavior and capabilities"
    )
    
    st.markdown("---")
    
    # Conversation info
    st.subheader("💬 Conversation Info")
    if "conversation_doc" in st.session_state and st.session_state.conversation_doc:
        conv_doc = st.session_state.conversation_doc
        st.write(f"**Session:** `{conv_doc['session_id'][:8]}...`")
        st.write(f"**Messages:** {len(conv_doc['messages'])}")
        created_utc = datetime.fromisoformat(conv_doc['created_at'].replace('Z', '+00:00'))
        cet = pytz.timezone('Europe/Zurich')
        created_cet = created_utc.astimezone(cet)
        st.write(f"**Created:** {created_cet.strftime('%H:%M:%S')} CET")
        
        if st.button("🔄 New Conversation"):
            # Cleanup current session
            for key in ["conversation_doc", "messages", "connected_agents", "agent_thread"]:
                if key in st.session_state:
                    del st.session_state[key]
            initialize_conversation()
            st.rerun()
    
    st.markdown("---")
    
    # Audio recorder
    st.subheader("🎙️ Voice Input")
    custom_audio_bytes = audio_recorder(
        text="Click to record",
        recording_color="#e8b62c",
        neutral_color="#6aa36f",
        icon_size="2x",
        sample_rate=41_000,
    )
    
    if custom_audio_bytes:
        st.session_state.voice_prompt = speech_to_text(custom_audio_bytes)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Main chat interface
conversation_container = st.container(height=600, border=False)

# Handle new messages
if text_prompt := st.chat_input("Ask me anything!"):
    prompt = text_prompt
elif custom_audio_bytes and "voice_prompt" in st.session_state:
    prompt = st.session_state.voice_prompt
    del st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display conversation history
        for message in st.session_state.messages:
            if message["role"] != "system":
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        
        # Process with multi-agent system
        with st.chat_message("assistant"):
            with st.spinner("🤔 Consulting with my specialized agents..."):
                result = multi_agent_chat(prompt)
            
            # Clean text for TTS (remove markdown and special characters)
            audio_text = re.sub(r'\([^)]*\)', '', result)
            audio_text = re.sub(r'[*_`#]', '', audio_text)
            
            st.markdown(result)
            
            # Play audio if enabled
            if st.session_state.voice_on:
                try:
                    audio_content = text_to_speech(audio_text)
                    st.audio(audio_content, format="audio/wav", autoplay=True)
                except Exception as e:
                    logger.error(f"TTS error: {e}")
                    st.warning("Could not generate audio for this response")
        
        # Add assistant response to messages
        st.session_state.messages.append({"role": "assistant", "content": result})
    
    else:
        # Display existing conversation
        for message in st.session_state.messages:
            if message["role"] != "system":
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

# Cleanup on app shutdown (this runs when the script ends)
import atexit
atexit.register(cleanup_agents)
