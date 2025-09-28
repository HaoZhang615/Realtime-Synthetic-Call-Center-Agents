"""Backend assistant service that orchestrates conversational agents."""

from __future__ import annotations

import copy
import inspect
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from backend.agents.assistant_agent import assistant_agent
from backend.agents.database_agent import database_agent
from backend.agents.internal_kb import internal_kb_agent
from backend.agents.root import root_assistant
from backend.agents.web_search_agent import web_search_agent

logger = logging.getLogger(__name__)

_AGENT_ID_PATTERN = re.compile(r"assistant", re.IGNORECASE)


class AssistantService:
    """Manage agent registration and tool invocation for a conversation."""

    def __init__(self, language: str = "English") -> None:
        self.language = language
        self.agents: Dict[str, Dict[str, Any]] = {}

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
        return list(agent_tools)

    def _other_agents_as_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Expose every other agent as a tool for the active agent."""
        tools: List[Dict[str, Any]] = []
        for other_id, config in self.agents.items():
            if other_id == agent_id:
                continue
            tools.append(
                {
                    "name": config["id"],
                    "description": config.get("description", ""),
                    "parameters": {"type": "object", "properties": {}},
                    "returns": (
                        lambda _params, target=config["id"]: target  # noqa: E731
                    ),
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
        logger.debug(
            "Handling tool invocation %s with parameters %s", tool_name, parameters
        )
        tools = list(self._iterate_tools())
        tool = next((item for item in tools if item["name"] == tool_name), None)
        if tool is None:
            logger.warning("Received unknown tool invocation: %s", tool_name)
            return {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": f"Tool {tool_name} is not available.",
                },
            }

        if _AGENT_ID_PATTERN.search(tool_name):
            logger.debug("Switching active agent to %s", tool_name)
            agent = self.agents[tool_name]
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
        if callable(returns):
            if inspect.iscoroutinefunction(returns):
                result = await returns(parameters)
            else:
                result = returns(parameters)
        else:
            result = returns

        logger.debug("Tool %s completed", tool_name)
        return {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
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
        self.assistant_service = AssistantService(language=language)

    def initialise_agents(self, customer_id: str) -> None:
        """Register core agents for the supplied customer identifier."""
        self.assistant_service.register_agent(internal_kb_agent)
        self.assistant_service.register_agent(database_agent(customer_id))
        self.assistant_service.register_agent(assistant_agent)

        if os.getenv("BING_SEARCH_API_KEY"):
            self.assistant_service.register_agent(web_search_agent)

        self.assistant_service.register_root_agent(root_assistant(customer_id))
        logger.info("Initialised agents for customer %s", customer_id)

    async def handle_tool_call(
        self, tool_name: str, parameters: Dict[str, Any], call_id: str
    ) -> Dict[str, Any]:
        """Proxy tool invocation to the underlying assistant service."""
        return await self.assistant_service.get_tool_response(
            tool_name=tool_name, parameters=parameters, call_id=call_id
        )
