"""FastAPI skeleton for Admin API.

Endpoints:
- POST /api/realtime/token       : returns a short-lived access token for browser realtime clients (AOAI/Realtime)
- POST /api/admin/upload         : accept multipart files and schedule processing using existing utils.upload_documents
- GET  /api/health               : basic health check

This module puts the repository's `src` folder on sys.path so existing utilities under
`src/backend/utils` can be imported as `utils.*` for an easy initial integration.

Note: For production, move long-running work to a queue/worker. Do not embed secrets in the
frontend; use managed identity + Key Vault.
"""

import logging
import os
import sys
import tempfile
import shutil
from typing import List

# Ensure repo `src` directory is importable so we can `import utils.*` like existing pages do.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # <repo>/src
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # <repo>/src/backend
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents import SearchClient
from pydantic import BaseModel

# Import existing utilities from the repo
from utils.file_processor import upload_documents, setup_index
from utils.data_synthesizer import DataSynthesizer, run_synthesis
from load_azd_env import load_azd_environment

# Load environment variables automatically
load_azd_environment()

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Realtime Admin API")

# Configure CORS for React dev server by default
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

credential = DefaultAzureCredential()


# Response models
class FileInfo(BaseModel):
    name: str
    size: int
    last_modified: str
    url: str


class SynthesisRequest(BaseModel):
    company_name: str
    num_customers: int
    num_products: int
    num_conversations: int


class BulkDeleteRequest(BaseModel):
    filenames: List[str]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/realtime/token")
async def get_realtime_token():
    """Return a short-lived token for browser realtime clients.

    The implementation uses DefaultAzureCredential to request a token for a scope defined
    by AOAI_SCOPE. In local/dev environments where a credential is not available this
    will return a dev token placeholder; replace with a proper error or auth flow for
    production.
    """
    scope = os.getenv("AOAI_SCOPE", "https://cognitiveservices.azure.com/.default")
    try:
        token = credential.get_token(scope)
        return {"access_token": token.token, "expires_on": token.expires_on}
    except Exception as ex:  # pragma: no cover - depends on local env
        logger.warning("Could not acquire Azure token: %s", ex)
        # Helpful for local development — return a placeholder but do not use in production
        return {"access_token": "dev-token", "expires_on": 0}


def upload_with_setup(azure_credential, source_folder, indexer_name, azure_search_endpoint, azure_storage_endpoint, azure_storage_container):
    """Setup the search index infrastructure then upload documents."""
    try:
        logger.info("Setting up search index infrastructure...")
        
        # Get required environment variables for setup_index
        uami_id = os.getenv("AZURE_USER_ASSIGNED_IDENTITY_ID")
        index_name = os.getenv("AZURE_SEARCH_INDEX", "documents")
        azure_storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        embedding_endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
        azure_openai_embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        azure_openai_embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL")
        
        # For local dev, ensure AI Services key is available (bypass Key Vault resolution)
        ai_services_key = os.getenv("AZURE_AI_SERVICES_KEY")
        if not ai_services_key or ai_services_key.startswith("@Microsoft.KeyVault"):
            # If we have a Key Vault reference or no key, set a direct key for local dev
            # You need to get this from Azure Portal: AI Services -> Keys and Endpoint
            logger.warning("AZURE_AI_SERVICES_KEY is a Key Vault reference or missing. Set the direct key for local dev.")
            raise ValueError("Please set AZURE_AI_SERVICES_KEY to your actual AI Services key (not Key Vault reference) for local development")
        
        # Temporarily override the environment variable to bypass Key Vault resolution
        os.environ["AZURE_AI_SERVICES_KEY"] = ai_services_key
        
        # Convert embedding endpoint domain if needed (per Microsoft docs)
        if embedding_endpoint and "cognitiveservices.azure.com" in embedding_endpoint:
            embedding_endpoint = embedding_endpoint.replace("cognitiveservices.azure.com", "openai.azure.com")
        
        # Setup the index infrastructure
        setup_index(
            azure_credential=azure_credential,
            uami_id=uami_id,
            index_name=index_name,
            azure_search_endpoint=azure_search_endpoint,
            azure_storage_connection_string=azure_storage_connection_string,
            azure_storage_container=azure_storage_container,
            azure_openai_embedding_endpoint=embedding_endpoint,
            azure_openai_embedding_deployment=azure_openai_embedding_deployment,
            azure_openai_embedding_model=azure_openai_embedding_model,
            azure_openai_embeddings_dimensions=3072
        )
        
        logger.info("Index setup completed, uploading documents...")
        
        # Now upload the documents
        upload_documents(azure_credential, source_folder, indexer_name, azure_search_endpoint, azure_storage_endpoint, azure_storage_container)
        
        logger.info("Upload and indexing completed successfully")
        
    except Exception as ex:
        logger.exception("Upload with setup failed: %s", ex)
        raise
    finally:
        shutil.rmtree(source_folder, ignore_errors=True)
        logger.info("Cleaned up temp folder: %s", source_folder)


@app.post("/api/admin/upload")
async def api_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Accepts a set of files, writes them to a temporary folder and schedules
    `utils.file_processor.upload_documents` to process that folder in the background.

    Environment variables used:
    - AZURE_SEARCH_INDEX or AZURE_SEARCH_INDEX_NAME
    - AZURE_SEARCH_ENDPOINT
    - AZURE_STORAGE_ENDPOINT
    - AZURE_STORAGE_CONTAINER

    NOTE: upload_documents currently runs synchronously in-process. For heavier loads
    consider using a queue + worker.
    """
    tmpdir = tempfile.mkdtemp(prefix="upload_")
    try:
        for f in files:
            dest = os.path.join(tmpdir, f.filename)
            with open(dest, "wb") as out:
                out.write(await f.read())

        # Resolve parameters from environment
        azure_credential = DefaultAzureCredential()
        index_name = os.getenv("AZURE_SEARCH_INDEX") or os.getenv("AZURE_SEARCH_INDEX_NAME") or "sample-index"
        indexer_name = f"{index_name}-indexer"
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_storage_endpoint = os.getenv("AZURE_STORAGE_ENDPOINT")
        azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER") or os.getenv("AZURE_STORAGE_CONTAINER_NAME") or "ingest"

        logger.info("Scheduling upload_documents: indexer=%s, search=%s, storage=%s", indexer_name, azure_search_endpoint, azure_storage_endpoint)

        # Schedule the existing synchronous function in FastAPI background tasks
        background_tasks.add_task(
            upload_with_setup,
            azure_credential,
            tmpdir,
            indexer_name,
            azure_search_endpoint,
            azure_storage_endpoint,
            azure_storage_container,
        )

        return {"status": "accepted", "files": [f.filename for f in files]}
    except Exception as ex:
        shutil.rmtree(tmpdir, ignore_errors=True)
        logger.exception("Upload failed: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/admin/files")
async def list_files():
    """List all uploaded files in the storage container."""
    try:
        azure_storage_endpoint = os.getenv("AZURE_STORAGE_ENDPOINT")
        azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "documents")
        
        blob_client = BlobServiceClient(account_url=azure_storage_endpoint, credential=credential)
        container_client = blob_client.get_container_client(azure_storage_container)
        
        files = []
        for blob in container_client.list_blobs():
            files.append(FileInfo(
                name=blob.name,
                size=blob.size,
                last_modified=blob.last_modified.isoformat(),
                url=f"{azure_storage_endpoint}/{azure_storage_container}/{blob.name}"
            ))
        
        return {"files": files}
    except Exception as ex:
        logger.exception("Failed to list files: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@app.delete("/api/admin/files/{filename}")
async def delete_file(filename: str):
    """Delete a specific file from storage and search index."""
    try:
        azure_storage_endpoint = os.getenv("AZURE_STORAGE_ENDPOINT")
        azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "documents")
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_search_index = os.getenv("AZURE_SEARCH_INDEX", "documents")
        
        # Initialize clients
        blob_client = BlobServiceClient(account_url=azure_storage_endpoint, credential=credential)
        container_client = blob_client.get_container_client(azure_storage_container)
        search_client = SearchClient(
            endpoint=azure_search_endpoint,
            index_name=azure_search_index,
            credential=credential
        )
        
        # Fetch all results and filter/group in Python (like Streamlit)
        all_results = list(search_client.search("*", select="title,chunk_id,parent_id"))
        # Group by title
        docs_to_delete = [doc for doc in all_results if doc.get('title') == filename]
        if docs_to_delete:
            documents_to_delete = [{"@search.action": "delete", "chunk_id": doc['chunk_id']} for doc in docs_to_delete]
            search_client.delete_documents(documents=documents_to_delete)
            logger.info("Deleted %d documents from search index for file: %s", len(documents_to_delete), filename)
        # Delete from blob storage
        blob_client_for_file = container_client.get_blob_client(filename)
        if blob_client_for_file.exists():
            blob_client_for_file.delete_blob()
            logger.info("Deleted blob: %s", filename)
        else:
            logger.warning("Blob not found: %s", filename)
        return {
            "status": "deleted",
            "filename": filename,
            "search_documents_deleted": len(docs_to_delete)
        }
    except Exception as ex:
        logger.exception("Failed to delete file: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/admin/files/bulk-delete")
async def bulk_delete_files(request: BulkDeleteRequest):
    """Delete multiple files from storage and search index."""
    try:
        azure_storage_endpoint = os.getenv("AZURE_STORAGE_ENDPOINT")
        azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "documents")
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_search_index = os.getenv("AZURE_SEARCH_INDEX", "documents")
        
        # Initialize clients
        blob_client = BlobServiceClient(account_url=azure_storage_endpoint, credential=credential)
        container_client = blob_client.get_container_client(azure_storage_container)
        search_client = SearchClient(
            endpoint=azure_search_endpoint,
            index_name=azure_search_index,
            credential=credential
        )
        
        deleted_files = []
        total_search_docs_deleted = 0
        
        # Fetch all results once
        all_results = list(search_client.search("*", select="title,chunk_id,parent_id"))
        for filename in request.filenames:
            try:
                docs_to_delete = [doc for doc in all_results if doc.get('title') == filename]
                if docs_to_delete:
                    documents_to_delete = [{"@search.action": "delete", "chunk_id": doc['chunk_id']} for doc in docs_to_delete]
                    search_client.delete_documents(documents=documents_to_delete)
                    total_search_docs_deleted += len(documents_to_delete)
                    logger.info("Deleted %d documents from search index for file: %s", len(documents_to_delete), filename)
                # Delete from blob storage
                blob_client_for_file = container_client.get_blob_client(filename)
                if blob_client_for_file.exists():
                    blob_client_for_file.delete_blob()
                    logger.info("Deleted blob: %s", filename)
                deleted_files.append(filename)
            except Exception as ex:
                logger.exception("Failed to delete file %s: %s", filename, ex)
                continue
        return {
            "status": "completed",
            "deleted_files": deleted_files,
            "failed_files": [f for f in request.filenames if f not in deleted_files],
            "total_search_documents_deleted": total_search_docs_deleted
        }
    except Exception as ex:
        logger.exception("Bulk delete failed: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/admin/synthesize")
async def synthesize_data(request: SynthesisRequest, background_tasks: BackgroundTasks):
    """Trigger data synthesis for CosmosDB."""
    try:
        background_tasks.add_task(
            run_synthesis_task,
            request.company_name,
            request.num_customers,
            request.num_products,
            request.num_conversations
        )
        return {
            "status": "synthesis_started",
            "company_name": request.company_name,
            "num_customers": request.num_customers,
            "num_products": request.num_products,
            "num_conversations": request.num_conversations
        }
    except Exception as ex:
        logger.exception("Failed to start synthesis: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))

def run_synthesis_task(company_name: str, num_customers: int, num_products: int, num_conversations: int):
    """Background task to run data synthesis with parameters."""
    try:
        logger.info(f"Starting data synthesis: company={company_name}, customers={num_customers}, products={num_products}, conversations={num_conversations}")
        run_synthesis(company_name, num_customers, num_products, num_conversations)
        logger.info("Data synthesis completed successfully")
    except Exception as ex:
        logger.exception("Data synthesis failed: %s", ex)
        raise
