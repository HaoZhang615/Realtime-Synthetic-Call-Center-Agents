FastAPI Admin API — Development guide

This guide explains how to run the FastAPI admin API locally for development and wire it to the React dev server.

Prerequisites
- Python 3.11/3.12
- pip
- Node/npm for the frontend (the frontend dev server runs separately)

Install & run (PowerShell)

1. Create and activate a virtual environment
$ python -m venv .venv-api
$ .\.venv-api\Scripts\Activate.ps1

2. Install Python dependencies
$ pip install -r src/backend/requirements.txt

3. Set env variables (example values — replace with your configuration)
$env:AZURE_SEARCH_ENDPOINT = "https://<your-search>.search.windows.net"
$env:AZURE_STORAGE_ENDPOINT = "https://<yourstorage>.blob.core.windows.net"
$env:AZURE_STORAGE_CONTAINER = "ingest"
$env:AZURE_SEARCH_INDEX = "sample-index"
$env:FRONTEND_ORIGINS = "http://localhost:5173"
# Optionally set AOAI_SCOPE for realtime token requests
$env:AOAI_SCOPE = "https://cognitiveservices.azure.com/.default"

4. Run the API (development mode)
$ uvicorn api.main:app --reload --app-dir src/backend/api --port 8000

5. Run the frontend
- In a separate terminal: navigate to `src/frontend/react-app` and run `npm install` and `npm run dev`.
- Vite dev server is configured to proxy `/api` to `http://localhost:8000` — calls from the React app to `/api/*` will reach the FastAPI app.

Notes
- The current `/api/realtime/token` endpoint attempts to get an Azure access token using DefaultAzureCredential. For local development you can rely on `az login` or other local authentication.
- `api/admin/upload` writes uploaded files to a temporary folder and schedules `utils.file_processor.upload_documents` as a FastAPI background task. Move heavy processing to a dedicated worker or queue for production.
- The Dockerfile for this API is `src/backend/Dockerfile.fastapi`.
