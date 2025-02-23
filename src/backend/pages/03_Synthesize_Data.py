import streamlit as st
import os
import sys
import json
import logging
from azure.identity import DefaultAzureCredential
from utils.data_synthesizer import run_synthesis

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

products_folder_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'Products_and_Urls_List')
json_file_path = None
for file_name in os.listdir(products_folder_path):
    if file_name.endswith('.json'):
        json_file_path = os.path.join(products_folder_path, file_name)
        break

if json_file_path:
    with open(json_file_path, 'r') as file:
        data = json.load(file)
    st.session_state.products = data['products']
    st.session_state.urls = data['urls']

    # set target_company variable to the first word of the filename separated by underscore and add it to the session state
    st.session_state.target_company = file_name.split('_')[0]
else:
    st.session_state.products = []
    st.session_state.urls = []
    st.session_state.target_company = "Unknown"

# Load the common CSS
load_css("pages/common.css")

def count_json_files(folder_name):
    path = os.path.join(os.path.dirname(__file__), '..', 'assets', folder_name)
    return len([f for f in os.listdir(path) if f.endswith('.json')])

# Count files in each Cosmos folder
folders = {
    'customer': 'Cosmos_Customer',
    'product': 'Cosmos_Product',
    'purchase': 'Cosmos_Purchases',
    'human_conversation': 'Cosmos_HumanConversations'
}

counts = {k: count_json_files(v) for k, v in folders.items()}

# Assign counts to variables for backward compatibility
customer_count = counts['customer']
product_count = counts['product']
purchase_count = counts['purchase']
human_conversation_count = counts['human_conversation']

col1, col2, col3, col4, col5 = st.columns([3, 5, 6, 6, 2])
with col1:
    st.write("The synthesized products are:")
    for product in st.session_state.products:
        st.markdown(f"- **{product}**",)
with col2:
    st.write("The Bing Search is grounded by:")
    for url in st.session_state.urls:
        st.markdown(f"- **{url}**")
with col3:
    st.write(f"Current Company for synthesization: **{st.session_state.target_company}**")
    st.write(f"Number of customers synthesized: **{customer_count}**")
    st.write(f"Number of products synthesized: **{product_count}**")
    st.write(f"Number of purchases synthesized: **{purchase_count}**")
    st.write(f"Number of human conversations synthesized: **{human_conversation_count}**")
    st.markdown("---")
with col4:
    st.write("Enter the new company name for synthesization:")
    st.write("")
    st.write("Enter the number of customers to synthesize:")
    st.write("")
    st.write("Enter the number of products to synthesize:")
    st.write("")
    st.write("Enter the number of human conversations to synthesize:")
with col5:
    new_company = st.text_input("new company", key="new_company", label_visibility = "collapsed")  
    number_customer = st.text_input("number customer", key="number_customer", label_visibility = "collapsed")
    number_product = st.text_input("number product", key="number_product", label_visibility = "collapsed")
    number_human_conversation = st.text_input("number human conversation", key="number_human_conversation", label_visibility = "collapsed")
        
# Move the log placeholder outside of the column layout
log_placeholder = st.empty()
logs = []

# execute the synthesization process by clicking the button and call the notebook assets/scripts/SynthesizeEverything.ipynb
if st.button("Synthesize"):
    # Define a custom print function to capture output and update the styled container
    import builtins
    original_print = builtins.print
    def custom_print(*args, **kwargs):
        message = ' '.join(map(str, args))
        logs.append(message)
        # Build HTML content with a fixed height and scrollbar
        html_logs = f"<div style='height:25vh; overflow-y:auto; border:1px solid #ccc; padding:10px;'>{'<br>'.join(logs)}</div>"
        log_placeholder.markdown(html_logs, unsafe_allow_html=True)
        original_print(*args, **kwargs)

    builtins.print = custom_print

    try:
        params = {
            "company_name": new_company,
            "number_of_customers": int(number_customer),
            "number_of_product": int(number_product),
            "number_of_human_conversations": int(number_human_conversation)
        }
        original_print(f"Parameters: {params}")
        run_synthesis(
            company_name=params["company_name"],
            num_customers=params["number_of_customers"],
            num_products=params["number_of_product"],
            num_conversations=params["number_of_human_conversations"]
        )
    finally:
        builtins.print = original_print
