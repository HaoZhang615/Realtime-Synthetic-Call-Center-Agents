import asyncio
import pytest  # type: ignore[import]

from services.assistant_service import AssistantService
from websocket.realtime_handler import RealtimeHandler


class _DummyCredential:
    def get_token(self, scope: str):
        class _Token:
            token = "fake-token"

        return _Token()


@pytest.fixture
def assistant_service():
    service = AssistantService(language="English")

    sales_agent = {
        "id": "assistant_sales",
        "description": "Sales specialist agent",
        "system_message": "You are the sales agent speaking {language}.",
        "tools": [
            {
                "name": "lookup_order",
                "description": "Lookup an order by id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"}
                    },
                },
                "returns": lambda params: {
                    "order_id": params.get("order_id"),
                    "status": "processing",
                },
            }
        ],
    }

    concierge_agent = {
        "id": "assistant_root",
        "description": "Root concierge agent",
        "system_message": "You coordinate all agents in {language}.",
        "tools": [],
    }

    service.register_agent(sales_agent)
    service.register_root_agent(concierge_agent)
    return service


def test_agent_switch_returns_session_update(assistant_service: AssistantService):
    response = asyncio.run(
        assistant_service.get_tool_response(
            tool_name="assistant_sales", parameters={}, call_id="call-1"
        )
    )

    assert response["type"] == "session.update"
    session = response["session"]
    assert session["instructions"].startswith("You are the sales agent")
    assert any(tool["name"] == "assistant_root" for tool in session["tools"])


def test_tool_invocation_returns_conversation_item(assistant_service: AssistantService):
    response = asyncio.run(
        assistant_service.get_tool_response(
            tool_name="lookup_order",
            parameters={"order_id": "12345"},
            call_id="call-2",
        )
    )

    assert response["type"] == "conversation.item.create"
    item = response["item"]
    assert item["type"] == "function_call_output"
    assert item["call_id"] == "call-2"
    assert "12345" in str(item["output"])


def test_compose_session_update_merges_defaults(monkeypatch):
    monkeypatch.setattr(
        "websocket.realtime_handler.DefaultAzureCredential",
        lambda: _DummyCredential(),
    )
    handler = RealtimeHandler()

    merged = handler._compose_session_update(
        "session-1",
        {
            "instructions": "Use the concierge voice",
            "tools": [{"name": "assistant_sales"}],
        },
    )

    assert merged["instructions"] == "Use the concierge voice"
    assert merged["voice"] == handler.default_session_config["voice"]
    assert handler.session_state["session-1"]["tools"][0]["name"] == "assistant_sales"

    follow_up = handler._compose_session_update(
        "session-1",
        {
            "turn_detection": {"type": "server_vad", "threshold": 0.55},
        },
    )

    assert follow_up["turn_detection"]["threshold"] == 0.55
    assert follow_up["instructions"] == "Use the concierge voice"
