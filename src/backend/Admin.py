import os
import logging
import sys
import streamlit as st
from azure.monitor.opentelemetry import configure_azure_monitor
import util

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

logging.captureWarnings(True)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO").upper())
# Raising the azure log level to WARN as it is too verbose
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())

if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

logger = logging.getLogger(__name__)
logger.debug("Starting admin app")

# Load environment variables
util.load_dotenv_from_azd()

st.set_page_config(
    page_title="Admin",
    page_icon=":studio_microphone:",
    layout="wide",
    menu_items=None,
)

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load the common CSS
load_css("pages/common.css")

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.image(os.path.join("images", "logo.png"))

st.write("# Agentic Voice Assistant Solution Accelerator")
st.write("## Admin Interface")

st.write(
    """
    Welcome to the admin interface. Use the navigation menu on the left to:
    
    * **Ingest Documents**: Upload documents (.pdf, .docx, etc.) to be processed and added to the knowledge base
    * **Delete Documents**: Remove documents from the knowledge base when they are no longer needed
    * **Synthesize Data**: Generate synthetic data to simulate a **Contact Center** scenario with a database comprised of product, customer, purchases history, human agent conversations and AI agent concersations.
    """
)
