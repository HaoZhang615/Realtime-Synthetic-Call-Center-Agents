"""Backend assistant service that orchestrates conversational agents."""

from __future__ import annotations

import copy
import inspect
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from services.mcp_client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)

try:
    from agents.assistant_agent import assistant_agent
    logger.info("Successfully imported assistant_agent")
except Exception as e:
    logger.error(f"Failed to import assistant_agent: {e}")
    assistant_agent = None

try:
    from agents.database_agent import database_agent
    logger.info("Successfully imported database_agent")
except Exception as e:
    logger.error(f"Failed to import database_agent: {e}")
    database_agent = None

try:
    from agents.internal_kb import get_internal_kb_agent
    logger.info("Successfully imported get_internal_kb_agent")
except Exception as e:
    logger.error(f"Failed to import get_internal_kb_agent: {e}")
    get_internal_kb_agent = None

try:
    from agents.web_search_agent import web_search_agent
    logger.info("Successfully imported web_search_agent")
except Exception as e:
    logger.error(f"Failed to import web_search_agent: {e}")
    web_search_agent = None

try:
    from agents.root import root_assistant
    logger.info("Successfully imported root_assistant")
except Exception as e:
    logger.error(f"Failed to import root_assistant: {e}")
    root_assistant = None

_AGENT_ID_PATTERN = re.compile(r"assistant", re.IGNORECASE)


class AssistantService:
    """Manage agent registration and tool invocation for a conversation."""

    def __init__(self, language: str = "English") -> None:
        self.language = language
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.mcp_client: Optional[MCPClient] = None
        self._mcp_initialized = False
    
    async def initialize_mcp_client(self) -> None:
        """
        Initialize MCP client for AI Foundry web search.
        
        Called lazily on first use. Safe to call multiple times.
        """
        if self._mcp_initialized:
            return
        
        try:
            mcp_url = os.getenv("AZURE_AI_FOUNDRY_MCP_URL")
            if not mcp_url:
                logger.warning("AZURE_AI_FOUNDRY_MCP_URL not set - web search will not be available")
                return
            
            self.mcp_client = MCPClient(base_url=mcp_url)
            await self.mcp_client.initialize()
            self._mcp_initialized = True
            logger.info("✅ MCP Client initialized successfully for web search")
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self.mcp_client = None
    
    async def search_web_ai_foundry(self, query: str) -> str:
        """
        Execute web search via AI Foundry Agent MCP Server.
        
        Args:
            query: Search query
            
        Returns:
            Search results as text
        """
        if not self._mcp_initialized:
            await self.initialize_mcp_client()
        
        if not self.mcp_client:
            return "Web search is currently unavailable. Please try again later."
        
        try:
            result = await self.mcp_client.search_web(query)
            return result
        except MCPClientError as e:
            logger.error(f"Web search failed: {e}")
            return f"I encountered an error while searching: {str(e)}"

    def register_agent(self, agent: Dict[str, Any]) -> None:
        """Register a non-root agent definition."""
        agent_copy = copy.deepcopy(agent)
        agent_copy["system_message"] = self._format_string(
            agent_copy.get("system_message", ""),
            {"language": self.language},
        )
        self.agents[agent_copy["id"]] = agent_copy
        logger.debug("Registered agent %s", agent_copy["id"])

    def register_root_agent(self, agent: Dict[str, Any]) -> None:
        """Register the concierge agent and expose it as a tool to others."""
        agent_copy = copy.deepcopy(agent)
        agent_copy["system_message"] = self._format_string(
            agent_copy.get("system_message", ""),
            {"language": self.language},
        )
        root_id = agent_copy["id"]

        for agent_cfg in self.agents.values():
            if not any(tool.get("name") == root_id for tool in agent_cfg["tools"]):
                agent_cfg["tools"].append(
                    {
                        "name": root_id,
                        "description": (
                            "Switch back to the concierge agent when the "
                            "request falls outside your scope."
                        ),
                        "parameters": {"type": "object", "properties": {}},
                        "returns": (
                            lambda _params, target=root_id: target  # noqa: E731
                        ),
                    }
                )

        self.agents["root"] = agent_copy
        self.agents[root_id] = agent_copy
        logger.debug("Registered root agent %s", root_id)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Return a previously registered agent configuration."""
        return self.agents.get(agent_id)

    def _agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Return a list of tool definitions for the supplied agent."""
        agent = self.agents[agent_id]
        agent_tools = agent.get("tools", [])
        
        # Convert to Azure OpenAI Realtime-compatible format
        realtime_tools = []
        for tool in agent_tools:
            realtime_tool = {
                "type": "function",
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}})
            }
            realtime_tools.append(realtime_tool)
        
        return realtime_tools

    def _other_agents_as_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Expose every other agent as a tool for the active agent."""
        tools: List[Dict[str, Any]] = []
        for other_id, config in self.agents.items():
            if other_id == agent_id:
                continue
            tools.append(
                {
                    "type": "function",
                    "name": config["id"],
                    "description": config.get("description", ""),
                    "parameters": {"type": "object", "properties": {}},
                }
            )
        return tools

    def get_tools_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """Return the full toolset (real tools + agent switches)."""
        return self._agent_tools(agent_id) + self._other_agents_as_tools(agent_id)

    async def get_tool_response(
        self, tool_name: str, parameters: Dict[str, Any], call_id: str
    ) -> Dict[str, Any]:
        """Execute a tool call or return a routing instruction."""
        import time
        start_time = time.perf_counter()
        
        logger.debug(
            "[AssistantService] Starting tool invocation: %s with parameters %s", tool_name, parameters
        )
        tools = list(self._iterate_tools())
        tool = next((item for item in tools if item["name"] == tool_name), None)
        if tool is None:
            logger.warning("[AssistantService] Unknown tool invocation: %s", tool_name)
            return {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": f"Tool {tool_name} is not available.",
                },
            }

        if _AGENT_ID_PATTERN.search(tool_name):
            logger.debug("[AssistantService] Switching active agent to %s", tool_name)
            agent = self.agents[tool_name]
            elapsed = time.perf_counter() - start_time
            logger.debug(f"[AssistantService] Agent switch completed in {elapsed:.4f}s")
            return {
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "instructions": self._format_string(
                        agent.get("system_message", ""),
                        {"language": self.language},
                    ),
                    "tools": self.get_tools_for_agent(tool_name),
                },
            }

        returns = tool.get("returns")
        exec_start = time.perf_counter()
        if callable(returns):
            if inspect.iscoroutinefunction(returns):
                result = await returns(parameters)
            else:
                result = returns(parameters)
        else:
            result = returns
        exec_elapsed = time.perf_counter() - exec_start

        # Serialize result to JSON to measure serialization time
        serialize_start = time.perf_counter()
        if isinstance(result, str):
            output = result
        else:
            try:
                import json
                output = json.dumps(result)
            except Exception as e:
                logger.error(f"[AssistantService] Failed to serialize tool output for {tool_name}: {e}")
                output = str(result)
        serialize_elapsed = time.perf_counter() - serialize_start
        
        total_elapsed = time.perf_counter() - start_time
        logger.debug(
            f"[AssistantService] Tool {tool_name} completed in {total_elapsed:.4f}s "
            f"(exec: {exec_elapsed:.4f}s, serialize: {serialize_elapsed:.4f}s, output length: {len(output)} chars)"
        )
        
        return {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            },
        }

    def _iterate_tools(self) -> Iterable[Dict[str, Any]]:
        """Yield every tool definition across all registered agents."""
        for config in self.agents.values():
            for tool in config.get("tools", []):
                yield tool
            yield from self._other_agents_as_tools(config["id"])

    @staticmethod
    def _format_string(template: str, params: Dict[str, Any]) -> str:
        """Safely format a template string with the provided parameters."""
        if "{" not in template:
            return template
        try:
            return template.format(**params)
        except KeyError:
            logger.debug("Template %s could not be fully formatted", template)
            return template


class AgentOrchestrator:
    """High-level helper that wires all default agents for a session."""

    def __init__(self, language: str = "English") -> None:
        try:
            logger.info(f"Creating AssistantService with language: {language}")
            self.assistant_service = AssistantService(language=language)
            logger.info("AssistantService created successfully")
        except Exception as e:
            logger.error(f"Failed to create AssistantService: {e}")
            import traceback
            traceback.print_exc()
            self.assistant_service = None

    def initialise_agents(self, customer_id: str) -> None:
        """Register core agents for the supplied customer identifier."""
        if get_internal_kb_agent:
            # Get fresh agent definition with current topics from AI Search index
            # This ensures the description reflects the latest indexed documents
            self.assistant_service.register_agent(get_internal_kb_agent())
            logger.info("Registered internal KB agent with dynamic topics from AI Search")
        else:
            logger.warning("get_internal_kb_agent not available")
            
        if database_agent:
            self.assistant_service.register_agent(database_agent(customer_id))
        else:
            logger.warning("database_agent not available")
            
        if assistant_agent:
            self.assistant_service.register_agent(assistant_agent)
        else:
            logger.warning("assistant_agent not available")
        
        if web_search_agent:
            # Register web search agent with async tool
            agent_def = web_search_agent()
            # Link the tool's "returns" to the actual async method
            for tool in agent_def["tools"]:
                if tool["name"] == "search_web_ai_foundry":
                    tool["returns"] = self.assistant_service.search_web_ai_foundry
            self.assistant_service.register_agent(agent_def)
            logger.info("Registered web search agent")
        else:
            logger.warning("web_search_agent not available")

        if root_assistant:
            self.assistant_service.register_root_agent(root_assistant(customer_id))
        else:
            logger.warning("root_assistant not available")
            
        logger.info("Initialised agents for customer %s", customer_id)

    async def handle_tool_call(
        self, tool_name: str, parameters: Dict[str, Any], call_id: str
    ) -> Dict[str, Any]:
        """Proxy tool invocation to the underlying assistant service."""
        return await self.assistant_service.get_tool_response(
            tool_name=tool_name, parameters=parameters, call_id=call_id
        )
