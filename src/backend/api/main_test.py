"""
FastAPI Backend for WebSocket Testing

Minimal version for testing WebSocket connectivity.
"""

import logging
import os
import sys

# Ensure repo `src` directory is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # <repo>/src
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # <repo>/src/backend
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import route modules (skip admin for now due to dependencies)
from api.routes.realtime import realtime_router 
from api.routes.websocket import websocket_router

from load_azd_env import load_azd_environment

# Load environment variables automatically
load_azd_environment()

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Realtime WebSocket API (Test)")

# Configure CORS for React dev server by default
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(realtime_router, prefix="/api/realtime", tags=["realtime"])
app.include_router(websocket_router, prefix="/api", tags=["websocket"])


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "WebSocket API is running"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Realtime Synthetic Call Center Agents API - WebSocket Test Mode",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "session_config": "/api/session/config", 
            "transcription_config": "/api/transcription/config",
            "realtime_websocket": "ws://localhost:8000/api/realtime",
            "transcription_websocket": "ws://localhost:8000/api/transcription"
        }
    }