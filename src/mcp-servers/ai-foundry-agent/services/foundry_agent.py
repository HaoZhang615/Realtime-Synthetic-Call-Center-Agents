"""AI Foundry Agent Service with ephemeral threading and retry logic."""

import asyncio
import logging
import os
from typing import Any, Dict, Optional
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    Agent,
    AgentThread,
    MessageRole,
    RunStatus,
    BingGroundingTool,
)
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)


class AIFoundryAgentService:
    """
    Wrapper for Azure AI Foundry Agent API with ephemeral threading.
    
    Key Design Decisions:
    - Ephemeral Threads: Each search request creates a new thread (stateless)
    - Retry Logic: Network errors retry once, AI Foundry errors fail immediately
    - Timeout: 30s for AI Foundry agent execution
    - Agent Lifecycle: Agent created on startup, reused across requests
    """
    
    def __init__(
        self,
        endpoint: str,
        project_id: str,
        bing_connection_id: str,
        model_deployment: str,
        max_retries: int = 1,
        timeout_seconds: int = 30,
    ):
        """
        Initialize AI Foundry Agent Service.
        
        Args:
            endpoint: AI Foundry account endpoint (e.g., https://xxx.cognitiveservices.azure.com/)
            project_id: Full resource ID of the AI Foundry project
            bing_connection_id: Full resource ID of the Bing Search connection
            model_deployment: Model deployment name (e.g., gpt-4o-realtime-preview)
            max_retries: Maximum number of retries for network errors (default: 1)
            timeout_seconds: Maximum time to wait for agent execution (default: 30s)
        """
        self.endpoint = endpoint
        self.project_id = project_id
        self.bing_connection_id = bing_connection_id
        self.model_deployment = model_deployment
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        
        self.client: Optional[AIProjectClient] = None
        self.agent: Optional[Agent] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """
        Initialize AI Project client and create the agent.
        
        Agent is created once on startup and reused for all requests.
        Uses Managed Identity authentication (no keys required).
        """
        if self._initialized:
            logger.info("AI Foundry Agent Service already initialized")
            return
            
        try:
            logger.info("Initializing AI Foundry Agent Service...")
            logger.info(f"Endpoint: {self.endpoint}")
            logger.info(f"Project ID: {self.project_id}")
            logger.info(f"Model: {self.model_deployment}")
            
            # Build project endpoint from base endpoint and project resource ID
            # Expected format: https://<account>.services.ai.azure.com/api/projects/<project-name>
            # Extract project name from resource ID
            project_name = self.project_id.split("/")[-1]
            
            # Transform endpoint if needed (from cognitiveservices.azure.com to services.ai.azure.com)
            base_endpoint = self.endpoint.rstrip("/")
            if ".cognitiveservices.azure.com" in base_endpoint:
                # Transform: https://cog-xxx.cognitiveservices.azure.com -> https://cog-xxx.services.ai.azure.com
                base_endpoint = base_endpoint.replace(".cognitiveservices.azure.com", ".services.ai.azure.com")
                logger.info(f"Transformed endpoint to AI Foundry format: {base_endpoint}")
            
            # Build full project endpoint (azure-ai-projects 1.0.0 API)
            project_endpoint = f"{base_endpoint}/api/projects/{project_name}"
            logger.info(f"Project Endpoint: {project_endpoint}")
            
            # Create AI Project client with Managed Identity
            credential = DefaultAzureCredential()
            self.client = AIProjectClient(
                endpoint=project_endpoint,
                credential=credential,
            )
            
            # Create agent with Bing Grounding tool
            logger.info("Creating AI Foundry agent with Bing Search tool...")
            self.agent = await self._create_agent()
            
            self._initialized = True
            logger.info(f"✅ AI Foundry Agent initialized successfully: {self.agent.id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI Foundry Agent: {e}", exc_info=True)
            raise RuntimeError(f"AI Foundry Agent initialization failed: {e}") from e
    
    async def _create_agent(self) -> Agent:
        """Create the AI Foundry agent with Bing Search tool."""
        try:
            # Construct connection ID with proper casing
            # The bing_connection_id from env might be lowercased by Bicep
            # Extract the connection name and rebuild the ID with correct casing
            if "/" in self.bing_connection_id:
                # It's a full resource ID - extract just the connection name
                connection_name = self.bing_connection_id.split("/")[-1]
            else:
                # It's already just the connection name
                connection_name = self.bing_connection_id
            
            # Construct the connection ID with proper casing from the project ID
            # Project ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}
            # Connection ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/connections/{connection}
            if "/projects/" in self.project_id:
                # Replace "/projects/{project}" with "/connections/{connection}"
                base_path = self.project_id.rsplit("/projects/", 1)[0]
                properly_cased_connection_id = f"{base_path}/connections/{connection_name}"
            else:
                # Fallback to using the connection ID as-is
                properly_cased_connection_id = self.bing_connection_id
            
            logger.info(f"Using Bing connection: {properly_cased_connection_id}")
            
            # Define Bing Grounding tool using the properly cased connection ID
            bing_tool = BingGroundingTool(connection_id=properly_cased_connection_id)
            
            # Create agent
            agent = self.client.agents.create_agent(
                model=self.model_deployment,
                name="Web Search Agent",
                instructions=(
                    "You are a web search assistant powered by Bing Search. "
                    "When users ask questions that require current information, "
                    "use the Bing Grounding tool to search the web. "
                    "Provide concise, accurate answers based on the search results. "
                    "Always cite your sources when presenting information."
                ),
                tools=bing_tool.definitions,  # Use .definitions for azure-ai-projects 1.0.0
            )
            
            return agent
            
        except AzureError as e:
            logger.error(f"Azure API error creating agent: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating agent: {e}", exc_info=True)
            raise
    
    async def search_web(self, query: str) -> str:
        """
        Execute web search using AI Foundry agent with ephemeral threading.
        
        Creates a new thread for each request (stateless design).
        Implements retry logic for network errors only.
        
        Args:
            query: The search query
            
        Returns:
            Search result as string
            
        Raises:
            RuntimeError: If agent not initialized or execution fails
            TimeoutError: If agent execution exceeds timeout
        """
        if not self._initialized or not self.agent:
            raise RuntimeError("AI Foundry Agent not initialized. Call initialize() first.")
        
        logger.info(f"Executing web search: '{query}'")
        
        # Retry loop (for network errors only)
        last_exception = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                logger.warning(f"Retry attempt {attempt}/{self.max_retries}")
                await asyncio.sleep(1)  # Brief delay between retries
            
            try:
                return await self._execute_search_with_timeout(query)
                
            except (ConnectionError, TimeoutError) as e:
                # Network-related errors - retry
                last_exception = e
                logger.warning(f"Network error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
                    raise RuntimeError(f"Search failed after {self.max_retries + 1} attempts: {e}") from e
                    
            except AzureError as e:
                # Azure API errors - don't retry, fail immediately
                logger.error(f"Azure API error (no retry): {e}", exc_info=True)
                raise RuntimeError(f"AI Foundry API error: {e}") from e
                
            except Exception as e:
                # Other errors - don't retry
                logger.error(f"Unexpected error (no retry): {e}", exc_info=True)
                raise RuntimeError(f"Search execution failed: {e}") from e
        
        # Should not reach here, but just in case
        raise RuntimeError(f"Search failed: {last_exception}")
    
    async def _execute_search_with_timeout(self, query: str) -> str:
        """
        Execute search with timeout protection.
        
        Creates ephemeral thread, executes search, and cleans up.
        """
        try:
            # Execute with timeout
            return await asyncio.wait_for(
                self._execute_search_internal(query),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(f"Search timed out after {self.timeout_seconds}s")
            raise TimeoutError(f"Search execution exceeded {self.timeout_seconds} seconds")
    
    async def _execute_search_internal(self, query: str) -> str:
        """
        Internal search execution with ephemeral threading.
        
        Flow:
        1. Create thread (ephemeral)
        2. Add user message with query
        3. Create run and poll for completion
        4. Extract result from messages
        5. Delete thread (cleanup)
        """
        thread: Optional[AgentThread] = None
        
        try:
            # Step 1: Create ephemeral thread
            logger.debug("Creating ephemeral thread...")
            thread = self.client.agents.threads.create()
            logger.debug(f"Thread created: {thread.id}")
            
            # Step 2: Add user message
            logger.debug(f"Adding user message: '{query}' (type: {type(query).__name__})")
            
            # Ensure query is a string
            query_str = str(query) if not isinstance(query, str) else query
            
            self.client.agents.messages.create(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=query_str,
            )
            
            # Step 3: Create run and execute
            logger.debug("Creating run...")
            run = self.client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=self.agent.id,
            )
            logger.debug(f"Run created: {run.id}, Status: {run.status}")
            
            # Step 4: Check run status
            if run.status == RunStatus.FAILED:
                error_msg = f"Agent run failed: {getattr(run, 'last_error', 'Unknown error')}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            if run.status != RunStatus.COMPLETED:
                logger.warning(f"Unexpected run status: {run.status}")
            
            # Step 5: Extract result from messages
            logger.debug("Retrieving messages...")
            messages = self.client.agents.messages.list(thread_id=thread.id)
            
            # Convert to list to iterate
            messages_list = list(messages)
            
            # Find the agent's response (most recent message with role=agent)
            result_text = None
            for message in messages_list:
                # Compare role as string to handle both enum and string values
                role_str = str(message.role)
                message_role = role_str.split('.')[-1].lower() if '.' in role_str else role_str.lower()
                
                # Azure AI Foundry uses "AGENT" not "ASSISTANT"
                if message_role == "agent":
                    # Extract text from content
                    for content_item in message.content:
                        if hasattr(content_item, 'text') and content_item.text:
                            if hasattr(content_item.text, 'value'):
                                result_text = content_item.text.value
                            else:
                                # Maybe text is directly a string
                                result_text = str(content_item.text)
                            break
                    if result_text:
                        break
            
            if not result_text:
                logger.warning("No agent response found in messages")
                result_text = "No results found for the search query."
            
            logger.info(f"✅ Search completed successfully (length: {len(result_text)} chars)")
            return result_text
            
        finally:
            # Step 6: Cleanup - always delete the ephemeral thread
            if thread:
                try:
                    logger.debug(f"Deleting ephemeral thread: {thread.id}")
                    self.client.agents.threads.delete(thread.id)
                    logger.debug("Thread deleted successfully")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup thread {thread.id}: {cleanup_error}")
    
    async def cleanup(self) -> None:
        """
        Cleanup resources on shutdown.
        
        Deletes the agent (threads are already ephemeral and cleaned up per-request).
        """
        if self.agent and self.client:
            try:
                logger.info(f"Cleaning up agent: {self.agent.id}")
                self.client.agents.delete(self.agent.id)
                logger.info("Agent deleted successfully")
            except Exception as e:
                logger.warning(f"Failed to cleanup agent: {e}")
        
        self._initialized = False
        self.agent = None
        self.client = None
