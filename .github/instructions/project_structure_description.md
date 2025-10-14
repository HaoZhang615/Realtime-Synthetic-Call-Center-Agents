# Project Structure Description

This document describes the structure of the Realtime Synthetic Call Center Agents project to help GitHub Copilot understand the codebase organization.

## Overview

This project is organized into three main components, each with its own virtual environment and dependencies.

## Directory Structure

```
/
├── backend/                    # Backend API and services
│   ├── venv/                  # Python virtual environment for backend
│   ├── requirements.txt       # Python dependencies
│   └── [source files]         # Backend source code
│
├── frontend/                   # Frontend web application
│   ├── venv/                  # Python virtual environment for frontend
│   ├── requirements.txt       # Python dependencies
│   └── [source files]         # Frontend source code
│
└── mcp-servers/               # MCP (Model Context Protocol) servers
    ├── venv/                  # Python virtual environment for MCP servers
    ├── requirements.txt       # Python dependencies
    └── [source files]         # MCP server source code
```

## Component Details

### Backend (`/backend`)
- **Purpose**: API services and backend logic
- **Virtual Environment**: `backend/venv/`
- **Dependencies**: Managed via `backend/requirements.txt`

### Frontend (`/frontend`)
- **Purpose**: User interface and web application
- **Virtual Environment**: `frontend/venv/`
- **Dependencies**: Managed via `frontend/requirements.txt`

### MCP Servers (`/mcp-servers`)
- **Purpose**: Model Context Protocol server implementations
- **Virtual Environment**: `mcp-servers/venv/`
- **Dependencies**: Managed via `mcp-servers/requirements.txt`

## Important Notes

- Each component maintains its own isolated Python virtual environment
- Always activate the appropriate virtual environment when working on a specific component
- Dependencies are managed separately for each component to ensure proper isolation