"""
Admin Routes for FastAPI Backend

Contains all admin portal endpoints including file management,
data synthesis, and dashboard functionality.
"""

import logging
import os
import sys
import tempfile
import shutil
from typing import List, Optional
import uuid
from io import StringIO
import contextlib

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Query, Path
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents import SearchClient
from azure.cosmos import CosmosClient
from pydantic import BaseModel

# Import existing utilities from the repo
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))  # <repo>/src
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # <repo>/src/backend
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.file_processor import upload_documents, setup_index
from utils.data_synthesizer import DataSynthesizer, run_synthesis, logger as synthesizer_logger
from load_azd_env import load_azd_environment

# Load environment variables automatically
load_azd_environment()

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

admin_router = APIRouter()
credential = DefaultAzureCredential()

# Global job tracking
JOBS = {}

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

class BulkDeleteRequest(BaseModel):
    filenames: List[str]

class DashboardStats(BaseModel):
    documents_count: int
    total_storage_size: int
    index_name: str
    index_status: str
    last_updated: str
    vector_dimensions: int
    ai_conversations_count: int
    human_conversations_count: int

class ProductSentimentStats(BaseModel):
    product_name: str
    total_conversations: int
    positive: int
    negative: int
    neutral: int

class ConversationData(BaseModel):
    product: str
    sentiment: str
    agent_id: str
    conversation_date: Optional[str] = None
    messages: Optional[list] = None  # Array of {sender, message} objects
    topic: Optional[str] = None

class ConversationSentimentStats(BaseModel):
    products: List[ProductSentimentStats]
    overall_sentiment_distribution: dict
    total_conversations: int
    conversations: List[ConversationData]  # Raw conversation data for filtering


@admin_router.get("/dashboard")
async def get_dashboard_stats():
    """Get dashboard statistics including file count and search index info."""
    try:
        azure_storage_endpoint = os.getenv("AZURE_STORAGE_ENDPOINT")
        azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "documents")
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_search_index = os.getenv("AZURE_SEARCH_INDEX", "documents")
        
        # Get file statistics from blob storage
        blob_client = BlobServiceClient(account_url=azure_storage_endpoint, credential=credential)
        container_client = blob_client.get_container_client(azure_storage_container)
        
        files_count = 0
        total_size = 0
        last_modified = None
        
        if container_client.exists():
            for blob in container_client.list_blobs():
                files_count += 1
                total_size += blob.size
                if last_modified is None or blob.last_modified > last_modified:
                    last_modified = blob.last_modified
        
        # Get search index statistics
        try:
            search_client = SearchClient(
                endpoint=azure_search_endpoint,
                index_name=azure_search_index,
                credential=credential
            )
            
            # Try to get index stats by doing a count query
            index_status = "active"
            try:
                result = search_client.search("*", include_total_count=True, top=0)
                # Access total count (this triggers the search)
                _ = result.get_count()
            except Exception:
                index_status = "error"
                
        except Exception:
            index_status = "error"
        
        # Get Cosmos DB conversation counts
        ai_conversations_count = 0
        human_conversations_count = 0
        
        try:
            cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
            cosmos_database = os.getenv("COSMOSDB_DATABASE")
            
            if cosmos_endpoint and cosmos_database:
                cosmos_client = CosmosClient(cosmos_endpoint, credential)
                database = cosmos_client.get_database_client(cosmos_database)
                
                # Count AI_Conversations
                try:
                    ai_container = database.get_container_client("AI_Conversations")
                    ai_query = "SELECT VALUE COUNT(1) FROM c"
                    ai_results = list(ai_container.query_items(
                        query=ai_query,
                        enable_cross_partition_query=True
                    ))
                    ai_conversations_count = ai_results[0] if ai_results else 0
                except Exception as ex:
                    logger.warning("Failed to query AI_Conversations container: %s", ex)
                
                # Count Human_Conversations
                try:
                    human_container = database.get_container_client("Human_Conversations")
                    human_query = "SELECT VALUE COUNT(1) FROM c"
                    human_results = list(human_container.query_items(
                        query=human_query,
                        enable_cross_partition_query=True
                    ))
                    human_conversations_count = human_results[0] if human_results else 0
                except Exception as ex:
                    logger.warning("Failed to query Human_Conversations container: %s", ex)
        except Exception as ex:
            logger.warning("Failed to initialize Cosmos DB client: %s", ex)
        
        return DashboardStats(
            documents_count=files_count,
            total_storage_size=total_size,
            index_name=azure_search_index,
            index_status=index_status,
            last_updated=last_modified.isoformat() if last_modified else "2024-01-01T00:00:00Z",
            vector_dimensions=3072,  # Based on your embedding model configuration
            ai_conversations_count=ai_conversations_count,
            human_conversations_count=human_conversations_count
        )
        
    except Exception as ex:
        logger.exception("Failed to get dashboard stats: %s", ex)
        # Return default values on error
        return DashboardStats(
            documents_count=0,
            total_storage_size=0,
            index_name="documents",
            index_status="error",
            last_updated="2024-01-01T00:00:00Z",
            vector_dimensions=3072,
            ai_conversations_count=0,
            human_conversations_count=0
        )


@admin_router.get("/conversation-sentiment-stats")
async def get_conversation_sentiment_stats():
    """Get sentiment statistics for human conversations grouped by product."""
    try:
        cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
        cosmos_database = os.getenv("COSMOSDB_DATABASE")
        
        if not cosmos_endpoint or not cosmos_database:
            return ConversationSentimentStats(
                products=[],
                overall_sentiment_distribution={},
                total_conversations=0
            )
        
        cosmos_client = CosmosClient(cosmos_endpoint, credential)
        database = cosmos_client.get_database_client(cosmos_database)
        
        try:
            human_container = database.get_container_client("Human_Conversations")
            
            # Query all conversations with product, sentiment, agent_id, conversation_date, messages, and topic
            query = "SELECT c.product, c.sentiment, c.agent_id, c.conversation_date, c.messages, c.topic FROM c"
            conversations = list(human_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            # Aggregate data by product and sentiment
            product_stats = {}
            overall_sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}
            
            # Store raw conversations for frontend filtering
            conversations_data = []
            
            for conv in conversations:
                product = conv.get('product', 'Unknown')
                sentiment = conv.get('sentiment', 'neutral')
                agent_id = conv.get('agent_id', 'unknown')
                conversation_date = conv.get('conversation_date')
                messages = conv.get('messages', [])
                topic = conv.get('topic', 'Unknown')
                
                # Store conversation data
                conversations_data.append({
                    'product': product,
                    'sentiment': sentiment,
                    'agent_id': agent_id,
                    'conversation_date': conversation_date,
                    'messages': messages,
                    'topic': topic
                })
                
                # Initialize product if not exists
                if product not in product_stats:
                    product_stats[product] = {
                        'product_name': product,
                        'total_conversations': 0,
                        'positive': 0,
                        'negative': 0,
                        'neutral': 0
                    }
                
                # Count sentiments per product
                product_stats[product]['total_conversations'] += 1
                if sentiment in ['positive', 'negative', 'neutral']:
                    product_stats[product][sentiment] += 1
                
                # Count overall sentiments
                if sentiment in overall_sentiments:
                    overall_sentiments[sentiment] += 1
            
            # Convert to list of ProductSentimentStats
            products_list = [
                ProductSentimentStats(**stats) 
                for stats in product_stats.values()
            ]
            
            # Sort by total conversations descending
            products_list.sort(key=lambda x: x.total_conversations, reverse=True)
            
            return ConversationSentimentStats(
                products=products_list,
                overall_sentiment_distribution=overall_sentiments,
                total_conversations=len(conversations),
                conversations=conversations_data  # Include raw data for client-side filtering
            )
            
        except Exception as ex:
            logger.warning("Failed to query Human_Conversations for sentiment stats: %s", ex)
            return ConversationSentimentStats(
                products=[],
                overall_sentiment_distribution={},
                total_conversations=0,
                conversations=[]
            )
            
    except Exception as ex:
        logger.exception("Failed to get conversation sentiment stats: %s", ex)
        return ConversationSentimentStats(
            products=[],
            overall_sentiment_distribution={},
            total_conversations=0,
            conversations=[]
        )


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


@admin_router.post("/upload")
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


@admin_router.get("/files")
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


@admin_router.delete("/files/{filename}")
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


@admin_router.post("/files/bulk-delete")
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


class JobLogHandler(logging.Handler):
    """Logging handler that streams synthesizer logs directly into the JOBS structure."""
    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            job_status = JOBS.get(self.job_id)
            if job_status is not None:
                job_status["logs"].append(msg)
        except Exception:  # pragma: no cover
            pass


def run_synthesis_task(job_id: str, company_name: str, num_customers: int, num_products: int):
    """Background task to run data synthesis with parameters."""
    try:
        job_status = JOBS.get(job_id)
        if not job_status:
            logger.error("Job %s not found in JOBS dictionary", job_id)
            return

        def log(msg):
            job_status["logs"].append(msg)
            logger.info("Job %s: %s", job_id, msg)
        logger.info(f"Starting data synthesis: company={company_name}, customers={num_customers}, products={num_products}")

        # Attach real-time log handler to synthesizer logger
        job_handler = JobLogHandler(job_id)
        job_handler.setLevel(logging.INFO)
        job_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
        synthesizer_logger.addHandler(job_handler)

        # Create synthesizer instance
        import os
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')

        # Ensure the assets directory structure exists
        base_assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
        for dir_name in ['Cosmos_Customer', 'Cosmos_Product', 'Cosmos_Purchases', 'Cosmos_HumanConversations', 'Cosmos_ProductUrl']:
            os.makedirs(os.path.join(base_assets_dir, dir_name), exist_ok=True)

        synthesizer = DataSynthesizer(base_dir)

        # Initialize containers
        cosmos_producturl_container_name = "ProductUrl"
        cosmos_customer_container_name = "Customer"
        cosmos_product_container_name = "Product"
        cosmos_purchases_container_name = "Purchases"
        cosmos_human_conversations_container_name = "Human_Conversations"

        # Refresh Cosmos DB containers
        synthesizer.refresh_container(synthesizer.database, cosmos_producturl_container_name, "/company_name")
        synthesizer.refresh_container(synthesizer.database, cosmos_customer_container_name, "/customer_id")
        synthesizer.refresh_container(synthesizer.database, cosmos_product_container_name, "/product_id")
        synthesizer.refresh_container(synthesizer.database, cosmos_purchases_container_name, "/customer_id")
        synthesizer.refresh_container(synthesizer.database, cosmos_human_conversations_container_name, "/customer_id")

        # Step 1: Delete old data and create product URLs (20%)
        log("Step 1/5: Deleting old data and creating product URLs...")
        synthesizer.delete_json_files(synthesizer.base_dir)
        synthesizer.create_product_and_url_list(company_name, num_products)
        job_status["progress"] = 20

        # Step 2: Generate customers (40%)
        log("Step 2/5: Generating customer profiles...")
        synthesizer.synthesize_customer_profiles(num_customers)
        job_status["progress"] = 40

        # Step 3: Generate products (60%)
        log("Step 3/5: Generating product profiles...")
        synthesizer.synthesize_product_profiles(company_name)
        job_status["progress"] = 60

        # Step 4: Generate purchases (75%)
        log("Step 4/5: Generating purchases...")
        synthesizer.synthesize_purchases()
        job_status["progress"] = 75

        # Step 5: Generate conversations and save to Cosmos DB (100%)
        log("Step 5/5: Generating human conversations and saving to Cosmos DB...")
        synthesizer.synthesize_human_conversations()
        for folder, container in [
            ('Cosmos_ProductUrl', synthesizer.containers['product_url']),
            ('Cosmos_Customer', synthesizer.containers['customer']),
            ('Cosmos_Product', synthesizer.containers['product']),
            ('Cosmos_Purchases', synthesizer.containers['purchases']),
            ('Cosmos_HumanConversations', synthesizer.containers['human_conversations'])
        ]:
            synthesizer.save_json_files_to_cosmos_db(os.path.join(synthesizer.base_dir, folder), container)

        # Complete
        job_status["progress"] = 100
        job_status["status"] = "completed"
        log("Data synthesis completed successfully!")

        # Detach handler to avoid memory leaks for future jobs
        synthesizer_logger.removeHandler(job_handler)
        
    except Exception as ex:
        logger.exception("Data synthesis failed: %s", ex)
        if job_id in JOBS:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["logs"].append(f"Error: {str(ex)}")
        # Ensure handler removal if it was added
        for h in list(synthesizer_logger.handlers):
            if isinstance(h, JobLogHandler) and getattr(h, 'job_id', None) == job_id:
                synthesizer_logger.removeHandler(h)
        raise


@admin_router.post("/synthesize")
async def synthesize_data(request: SynthesisRequest, background_tasks: BackgroundTasks):
    """Trigger data synthesis for CosmosDB."""
    try:
        # Step-based progress tracking
        job_id = str(uuid.uuid4())
        job_status = {
            "progress": 0,
            "logs": [],
            "status": "started"
        }
        JOBS[job_id] = job_status

        background_tasks.add_task(
            run_synthesis_task,
            job_id,
            request.company_name,
            request.num_customers,
            request.num_products
        )

        return {"status": "synthesis_started", "job_id": job_id}
    except Exception as ex:
        logger.exception("Failed to start synthesis: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@admin_router.get("/job-status/{job_id}")
async def get_job_status(job_id: str = Path(...)):
    """
    Return the status, progress, and logs for a synthesis job.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job.get("status", "unknown"),
        "progress": job.get("progress", 0),
        "logs": job.get("logs", [])
    }