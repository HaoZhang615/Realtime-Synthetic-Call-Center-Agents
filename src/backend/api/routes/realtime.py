"""
Realtime API Routes

Provides HTTP endpoints for realtime API configuration and token management.
"""

import logging
import os
from fastapi import APIRouter
from azure.identity import DefaultAzureCredential

from load_azd_env import load_azd_environment

# Load environment variables automatically
load_azd_environment()

logger = logging.getLogger(__name__)

realtime_router = APIRouter()
credential = DefaultAzureCredential()


@realtime_router.post("/token")
async def get_realtime_token():
    """
    Return a short-lived token for browser realtime clients.

    The implementation uses DefaultAzureCredential to request a token for a scope defined
    by AOAI_SCOPE. In local/dev environments where a credential is not available this
    will return a dev token placeholder; replace with a proper error or auth flow for
    production.
    """
    scope = os.getenv("AOAI_SCOPE", "https://cognitiveservices.azure.com/.default")
    try:
        token = credential.get_token(scope)
        return {
            "access_token": token.token,
            "expires_on": token.expires_on,
            "websocket_url": os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "").replace("https://", "wss://"),
            "deployment": os.getenv("AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
        }
    except Exception as ex:  # pragma: no cover - depends on local env
        logger.warning("Could not acquire Azure token: %s", ex)
        # Helpful for local development — return a placeholder but do not use in production
        return {
            "access_token": "dev-token",
            "expires_on": 0,
            "websocket_url": "ws://localhost:8000/api/realtime", 
            "deployment": "dev-deployment",
            "api_version": "2024-10-01-preview"
        }