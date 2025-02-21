import streamlit as st
import os
import sys
import logging
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Delete Data",
    page_icon=os.path.join("images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load the common CSS
load_css("pages/common.css")

# CSS to hide table row index
hide_table_row_index = """
            <style>
            thead tr th:first-child {display:none}
            tbody th {display:none}
            </style>
            """
st.markdown(hide_table_row_index, unsafe_allow_html=True)

try:
    # Initialize Azure clients
    azure_credential = DefaultAzureCredential()
    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=os.environ["AZURE_SEARCH_INDEX"],
        credential=azure_credential
    )
    blob_client = BlobServiceClient(
        account_url=os.environ["AZURE_STORAGE_ENDPOINT"],
        credential=azure_credential
    )
    container_client = blob_client.get_container_client(os.environ["AZURE_STORAGE_CONTAINER"])

    # Get unique file names from search index
    results = search_client.search("*", select="title, parent_id", include_total_count=True)
    if results.get_count() == 0:
        st.info("No files to delete")
        st.stop()

    # Group results by title (filename)
    files = {}
    for result in results:
        title = result['title']
        if title not in files:
            files[title] = []
        files[title].append(result['parent_id'])

    st.write("Select files to delete:")
    
    with st.form("delete_form", clear_on_submit=True, border=False):
        selections = {
            filename: st.checkbox(filename, False, key=filename)
            for filename in files.keys()
        }
        selected_files = {
            filename: ids for filename, ids in files.items() if selections[filename]
        }

        if st.form_submit_button("Delete"):
            with st.spinner("Deleting files..."):
                if len(selected_files) == 0:
                    st.info("No files selected")
                    st.stop()
                else:
                    deleted_files = []
                    for filename, parent_ids in selected_files.items():
                        try:
                            # Delete from blob storage
                            blob_client = container_client.get_blob_client(filename)
                            if blob_client.exists():
                                blob_client.delete_blob()

                            # Delete from search index
                            filter_expression = " or ".join([f"parent_id eq '{parent_id}'" for parent_id in parent_ids])
                            search_client.delete_documents(
                                documents=[{"@search.action": "delete", "chunk_id": doc['chunk_id']} 
                                         for doc in search_client.search("*", filter=filter_expression, select="chunk_id")])
                            
                            deleted_files.append(filename)
                            
                        except Exception as e:
                            logger.error(f"Error deleting {filename}: {str(e)}")
                            st.error(f"Error deleting {filename}")
                            continue

                    if deleted_files:
                        st.success(f"Successfully deleted: {', '.join(deleted_files)}")
                        st.rerun()

except Exception as e:
    logger.error(f"Error: {str(e)}")
    st.error("An error occurred while loading or deleting files.")
