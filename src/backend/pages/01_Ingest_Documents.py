import os
import streamlit as st
import sys
import logging
import traceback
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.file_processor import setup_index, upload_documents

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Ingest Data",
    page_icon=":studio_microphone:",
    layout="wide",
    menu_items=None,
)

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load the common CSS
load_css("pages/common.css")

try:
    st.write("# Upload Documents")
    st.write("""
    Upload documents to be processed and indexed in Azure AI Search. 
    The documents will be automatically vectorized and made searchable.
    """)

    uploaded_files = st.file_uploader(
        "Choose files to upload",
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("Process Files"):
            with st.spinner("Uploading and processing files..."):
                # Create a temporary directory to store uploaded files
                import tempfile
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Save uploaded files to temporary directory
                    for uploaded_file in uploaded_files:
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                    azure_credential = DefaultAzureCredential()


                    # Ensure index and required components exist
                    setup_index(
                        azure_credential=azure_credential,
                        uami_id=os.environ["AZURE_USER_ASSIGNED_IDENTITY_ID"],
                        index_name=os.environ["AZURE_SEARCH_INDEX"],
                        azure_search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
                        azure_storage_connection_string=os.environ["AZURE_STORAGE_CONNECTION_STRING"],
                        azure_storage_container=os.environ["AZURE_STORAGE_CONTAINER"],
                        azure_openai_embedding_endpoint=os.environ["AZURE_OPENAI_EMBEDDING_ENDPOINT"],
                        azure_openai_embedding_deployment=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
                        azure_openai_embedding_model=os.environ["AZURE_OPENAI_EMBEDDING_MODEL"],
                        azure_openai_embeddings_dimensions=3072
                    )

                    # Upload documents and trigger indexing
                    upload_documents(
                        azure_credential=azure_credential,
                        source_folder=temp_dir,
                        indexer_name=os.environ["AZURE_SEARCH_INDEX"],
                        azure_search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
                        azure_storage_endpoint=os.environ["AZURE_STORAGE_ENDPOINT"],
                        azure_storage_container=os.environ["AZURE_STORAGE_CONTAINER"]
                    )

                st.success("""
                Files uploaded and processing started! 
                The indexing process will take a few minutes to complete.
                You can check the Azure AI Search indexer status in the Azure Portal for progress.
                """)

except Exception as e:
    logger.error(traceback.format_exc())
    st.error(f"An error occurred: {str(e)}")
