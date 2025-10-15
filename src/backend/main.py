"""
FastAPI Backend for Realtime Synthetic Call Center Agents

Provides both admin portal functionality and WebSocket endpoints for realtime voice communication.

Main endpoints:
- POST /api/realtime/token       : returns a short-lived access token for browser realtime clients (AOAI/Realtime)
- WS   /api/realtime             : WebSocket endpoint for real-time voice communication
- WS   /api/transcription        : WebSocket endpoint for real-time transcription
- POST /api/admin/upload         : accept multipart files and schedule processing using existing utils.upload_documents
- GET  /api/health               : basic health check

This module integrates the repository's existing utilities with new WebSocket infrastructure
for real-time voice communication.
"""

import logging
import os
import sys

# Ensure repo `src` directory is importable so we can `import utils.*` like existing pages do.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # <repo>/src
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # <repo>/src/backend
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Import route modules
from routes.admin import admin_router
from routes.realtime import realtime_router 
from routes.websocket import websocket_router
from routes.customers import router as customers_router
from routes.conversations import router as conversations_router

from load_azd_env import load_azd_environment

# Load environment variables automatically
load_azd_environment()

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Realtime Admin API")

# Configure CORS for React dev server by default
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:5001,http://localhost:5000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with their respective prefixes
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(realtime_router, prefix="/api/realtime", tags=["realtime"])
app.include_router(websocket_router, prefix="/api", tags=["websocket"])
app.include_router(customers_router, prefix="/api", tags=["customers"])
app.include_router(conversations_router, prefix="/api", tags=["conversations"])


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Redirect root to API documentation"""
    return RedirectResponse(url="/docs", status_code=301)