"""
Realtime Handler for Azure OpenAI WebSocket Bridge

Handles the connection between browser WebSockets and Azure OpenAI Realtime API.
Integrates with existing RealtimeClient and AssistantService architecture.
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from typing import Optional, Dict, Any
import websockets
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential, CredentialUnavailableError
from fastapi import WebSocket, WebSocketDisconnect

# Import existing components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    from services.assistant_service import AgentOrchestrator
    logging.info("Successfully imported AgentOrchestrator")
except ImportError as e:
    logging.error(f"Could not import AgentOrchestrator: {e} - using mock implementation")
    class AgentOrchestrator:
        def __init__(self, language="English"): 
            self.assistant_service = None
        def initialise_agents(self, customer_id): pass
        async def handle_tool_call(self, **kwargs): return {"result": "mock response"}
from load_azd_env import load_azd_environment

# Load environment
load_azd_environment()

logger = logging.getLogger(__name__)


class RealtimeHandler:
    """
    Handles real-time voice communication between browser and Azure OpenAI
    
    This class acts as a bridge, connecting the browser's WebSocket to Azure OpenAI's
    Realtime API while integrating with the existing multi-agent system.
    """
    
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.agent_orchestrator = AgentOrchestrator()
        self.customer_initialized = {}  # Track which customers have been initialized
        self.current_customer_id: Optional[str] = None
        self.active_agents: Dict[str, str] = {}
        self.session_state: Dict[str, Dict[str, Any]] = {}
        self.tool_call_timeout = float(os.getenv("TOOL_CALL_TIMEOUT_SECONDS", "15"))
        
        # Verify AgentOrchestrator is properly initialized
        if self.agent_orchestrator.assistant_service is None:
            logging.error("AgentOrchestrator.assistant_service is None!")
        else:
            logging.info("AgentOrchestrator.assistant_service initialized successfully")
        
        # Azure OpenAI configuration
        self.azure_endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "").replace("https://", "wss://")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
        self.deployment = os.getenv("AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT")
        self.scope = "https://cognitiveservices.azure.com/.default"
        
        # Session configuration
        self.default_session_config = {
            "modalities": ["text", "audio"],
            "voice": "shimmer",  # Default voice - will be overridden by frontend selection  
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {"type": "server_vad"},
            "tools": [],
            "tool_choice": "auto",
            "temperature": 0.8,
            "max_response_output_tokens": 4096,
        }

    def build_azure_headers(self) -> Dict[str, str]:
        """Build headers for Azure OpenAI WebSocket connection"""
        try:
            token = self.credential.get_token(self.scope)
            return {
                "Authorization": f"Bearer {token.token}",
                "x-ms-client-request-id": "realtime-voice-bot",
                "x-ms-useragent": "realtime-synthetic-call-center/1.0.0",
            }
        except Exception as e:
            logger.exception("Failed to build Azure headers: %s", e)
            raise

    def build_azure_ws_url(self) -> str:
        """Build Azure OpenAI WebSocket URL"""
        return f"{self.azure_endpoint}/openai/realtime?api-version={self.api_version}&deployment={self.deployment}"

    async def handle_client_message(
        self,
        message: Dict[str, Any],
        vendor_ws,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Process message from browser client before forwarding to Azure
        
        This allows us to intercept and modify messages, handle tool calls,
        and integrate with the existing agent system.
        """
        message_type = message.get("type")
        
        # Handle session updates to inject our agent configuration
        if message_type == "session.update":
            return await self._handle_session_update(message, customer_id, session_id)
        
        # Handle tool calls through our assistant service
        elif message_type == "conversation.item.create":
            return await self._handle_conversation_item(message)
            
        # Forward other messages as-is
        return message

    def ensure_customer_initialized(self, customer_id: Optional[str]):
        """Ensure the active customer context is synchronized with the agent graph."""
        if not customer_id:
            return

        if (customer_id not in self.customer_initialized or
                self.current_customer_id != customer_id):
            self.agent_orchestrator.initialise_agents(customer_id)
            self.customer_initialized[customer_id] = True
            self.current_customer_id = customer_id
            logger.info("Initialized agents for customer: %s", customer_id)

    async def _handle_session_update(
        self,
        message: Dict[str, Any],
        customer_id: str = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle session update to inject agent configuration"""
        session = message.get("session", {})
        
        # Safety check for agent_orchestrator
        if not self.agent_orchestrator:
            logging.error("agent_orchestrator is None!")
            return message
            
        if not self.agent_orchestrator.assistant_service:
            logging.error("agent_orchestrator.assistant_service is None!")
            return message
        
        # Ensure customer agents are initialized if customer_id provided
        if customer_id:
            self.ensure_customer_initialized(customer_id)
        
        # Start with root agent configuration
        root_agent = self.agent_orchestrator.assistant_service.get_agent("root")
        if root_agent:
            session["instructions"] = root_agent.get("system_message", session.get("instructions"))
            if session_id:
                self.active_agents[session_id] = root_agent.get("id", "root")
            
        # Get tools for root agent (includes other agents as tools)
        root_tools = self.agent_orchestrator.assistant_service.get_tools_for_agent("root")
        if root_tools:
            session["tools"] = root_tools
            
        # Merge with default configuration, giving priority to frontend settings
        # This ensures voice and other user preferences are preserved
        merged_session = {**self.default_session_config}
        merged_session.update(session)  # Frontend settings override defaults
        message["session"] = merged_session
        if session_id:
            self.session_state[session_id] = merged_session
        
        logger.info(f"Updated session config with agent: root, tools: {len(root_tools) if root_tools else 0}, voice: {merged_session.get('voice', 'not set')}")
        return message

    async def _handle_conversation_item(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversation item creation"""
        # For now, just forward the message
        # Later, we can add customer context injection here
        return message

    async def handle_azure_message(
        self,
        message: Dict[str, Any],
        session_id: str,
        vendor_ws: websockets.WebSocketClientProtocol,
    ) -> Optional[Dict[str, Any]]:
        """
        Process message from Azure OpenAI before forwarding to client
        
        This allows us to intercept tool calls and handle them through
        our existing assistant service.
        """
        message_type = message.get("type")
        
        # Handle tool calls
        if message_type == "response.function_call_arguments.done":
            await self._handle_tool_call(message, session_id, vendor_ws)
            
        # Forward message to client
        return message

    def _compose_session_update(
        self, session_id: str, overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge default, previously stored, and override session values."""
        base = {**self.default_session_config}
        previous = self.session_state.get(session_id) or {}
        base.update(previous)
        base.update(overrides)
        self.session_state[session_id] = base
        return base

    async def _handle_tool_call(
        self,
        message: Dict[str, Any],
        session_id: str,
        vendor_ws: websockets.WebSocketClientProtocol,
    ):
        """Handle tool calls through the assistant service"""
        try:
            item_id = message.get("item_id")
            call_id = message.get("call_id") 
            name = message.get("name")
            arguments = message.get("arguments", "{}")
            
            logger.info(f"Processing tool call: {name} for session {session_id}")
            
            if not name:
                logger.error("Tool call missing name field; aborting")
                await vendor_ws.send(
                    json.dumps(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({"error": "Tool name missing"}),
                            },
                        }
                    )
                )
                await vendor_ws.send(json.dumps({"type": "response.create"}))
                return None

            # Parse arguments
            try:
                parsed_args = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                parsed_args = {}
                
            logger.debug("Tool %s arguments: %s", name, parsed_args)

            # Call through assistant service
            assistant_service = self.agent_orchestrator.assistant_service
            if not assistant_service:
                logger.error("Assistant service not initialised; cannot handle tool call")
                return

            start_time = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    assistant_service.get_tool_response(
                        tool_name=name,
                        parameters=parsed_args,
                        call_id=call_id,
                    ),
                    timeout=self.tool_call_timeout,
                )
            except asyncio.TimeoutError:
                logger.exception(
                    "Tool %s timed out after %ss", name, self.tool_call_timeout
                )
                timeout_payload = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(
                            {"error": f"Tool {name} timed out."}
                        ),
                    },
                }
                await vendor_ws.send(json.dumps(timeout_payload))
                await vendor_ws.send(json.dumps({"type": "response.create"}))
                return None
            
            outbound_messages = []

            if result.get("type") == "session.update":
                agent = assistant_service.get_agent(name)
                if agent:
                    logger.info(f"Agent switched to: {agent['id']}")
                    self.active_agents[session_id] = agent["id"]

                session_payload = result.get("session", {})
                composed_session = self._compose_session_update(session_id, session_payload)
                outbound_messages.append({"type": "session.update", "session": composed_session})
            elif result.get("type") == "conversation.item.create":
                item = result.get("item", {})
                output = item.get("output")
                if isinstance(output, (dict, list)):
                    item["output"] = json.dumps(output)
                elif output is not None and not isinstance(output, str):
                    item["output"] = str(output)
                outbound_messages.append(result)
            else:
                outbound_messages.append(result)

            for outbound in outbound_messages:
                await vendor_ws.send(json.dumps(outbound))
                logger.debug("Sent vendor message: %s", outbound.get("type"))

            # Resume response generation after tool handling
            await vendor_ws.send(json.dumps({"type": "response.create"}))
            logger.debug("Requested new response after tool call")

            elapsed = time.perf_counter() - start_time
            logger.info("Tool %s handled in %.2fs", name, elapsed)

            return None
            
        except Exception as e:
            logger.exception(f"Tool call failed: {e}")
            error_payload = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({"error": str(e)}),
                },
            }
            await vendor_ws.send(json.dumps(error_payload))
            await vendor_ws.send(json.dumps({"type": "response.create"}))
            return None

    async def relay_messages(self, client_ws: WebSocket, vendor_ws, session_id: str, customer_id: Optional[str] = None):
        """
        Relay messages bidirectionally between client and Azure OpenAI
        
        This is the core bridge function that handles all message routing.
        """
        
        async def client_to_vendor():
            """Forward messages from browser client to Azure OpenAI"""
            try:
                while True:
                    message = await client_ws.receive()
                    
                    # Handle WebSocket disconnect
                    if message.get("type") == "websocket.disconnect":
                        raise WebSocketDisconnect
                    
                    # Handle text messages (JSON)
                    if "text" in message:
                        try:
                            payload = json.loads(message["text"])
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON from client")
                            continue
                            
                        # Process message through handler
                        processed = await self.handle_client_message(
                            payload,
                            vendor_ws,
                            customer_id,
                            session_id,
                        )
                        if processed:
                            await vendor_ws.send(json.dumps(processed))
                            
                            # Log non-audio message types
                            if payload.get("type") not in {
                                "input_audio_buffer.append", 
                                "response.audio.delta"
                            }:
                                logger.debug(f"Client->Azure: {payload.get('type')}")
                    
                    # Handle binary messages
                    elif "bytes" in message and message["bytes"]:
                        logger.debug("Received binary data from client - not supported yet")
                        
            except WebSocketDisconnect:
                logger.info("Client WebSocket disconnected")
            except Exception as e:
                logger.exception(f"Error in client_to_vendor: {e}")

        async def vendor_to_client():
            """Forward messages from Azure OpenAI to browser client"""
            try:
                while True:
                    data = await vendor_ws.recv()
                    
                    # Parse Azure response
                    try:
                        azure_message = json.loads(data)
                        msg_type = azure_message.get("type")
                        
                        # Log all Azure messages for debugging
                        if msg_type not in {"response.audio.delta", "input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped"}:
                            logger.info(f"Azure->Client: {msg_type} - {azure_message}")
                        elif msg_type in {"response.audio.delta"}:
                            logger.debug(f"Azure->Client: {msg_type} (audio data)")
                        else:
                            logger.debug(f"Azure->Client: {msg_type}")
                            
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON from Azure")
                        continue
                        
                    # Process message through handler
                    processed = await self.handle_azure_message(azure_message, session_id, vendor_ws)
                    if processed:
                        await client_ws.send_text(json.dumps(processed))
                    else:
                        logger.warning(f"Processed message was None for type: {msg_type}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.info("Azure WebSocket disconnected")
            except Exception as e:
                logger.exception(f"Error in vendor_to_client: {e}")

        # Run both relay tasks concurrently
        tasks = [
            asyncio.create_task(client_to_vendor()),
            asyncio.create_task(vendor_to_client())
        ]
        
        try:
            # Wait for either task to complete (indicating connection closed)
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                    
        except Exception as e:
            logger.exception(f"Error in message relay: {e}")

    async def create_azure_connection(self) -> websockets.WebSocketClientProtocol:
        """Create WebSocket connection to Azure OpenAI"""
        headers = self.build_azure_headers()
        url = self.build_azure_ws_url()
        
        logger.info(f"Connecting to Azure OpenAI: {url}")
        
        try:
            return await websockets.connect(url, additional_headers=headers)
        except websockets.exceptions.InvalidHandshake as e:
            logger.error(f"Azure WebSocket handshake failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Failed to connect to Azure OpenAI: {e}")
            raise

    async def handle_session(self, client_ws: WebSocket, session_id: str, customer_id: Optional[str] = None):
        """
        Handle a complete voice session
        
        This is the main entry point for handling a WebSocket session.
        """
        logger.info(f"Starting voice session {session_id} for customer {customer_id}")
        
        try:
            # Create Azure OpenAI connection
            vendor_ws = await self.create_azure_connection()
            
            try:
                # Start message relay
                await self.relay_messages(client_ws, vendor_ws, session_id, customer_id)
            finally:
                # Ensure Azure connection is closed
                await vendor_ws.close()
                
        except (CredentialUnavailableError, ClientAuthenticationError) as e:
            error_msg = f"Azure authentication failed: {e}"
            logger.error(error_msg)
            try:
                await client_ws.send_text(json.dumps({
                    "type": "error",
                    "error": error_msg
                }))
            except:
                pass
        except Exception as e:
            logger.exception(f"Voice session {session_id} failed: {e}")
            try:
                await client_ws.send_text(json.dumps({
                    "type": "error", 
                    "error": f"Session error: {str(e)}"
                }))
            except:
                pass


# Global handler instance
realtime_handler = RealtimeHandler()