import streamlit as st
import os
import sys
import json
import logging
from azure.identity import DefaultAzureCredential
from utils.data_synthesizer import run_synthesis

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
logger = logging.getLogger(__name__)

# Ensure the assets directory structure exists for Swiss roadside assistance
base_assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
for dir_name in ['Cosmos_Customer', 'Cosmos_Vehicles', 'Cosmos_AssistanceCases', 'Cosmos_HumanConversations', 'Cosmos_ServiceTypes']:
    os.makedirs(os.path.join(base_assets_dir, dir_name), exist_ok=True)

st.set_page_config(
    page_title="Synthesize Swiss Roadside Assistance Data",
    page_icon=":red_car:",
    layout="wide",
    menu_items=None,
)

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

services_folder_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'Cosmos_ServiceTypes')
json_file_path = None
if os.path.exists(services_folder_path):
    for file_name in os.listdir(services_folder_path):
        if file_name.endswith('.json'):
            json_file_path = os.path.join(services_folder_path, file_name)
            break

if json_file_path:
    with open(json_file_path, 'r') as file:
        data = json.load(file)
    st.session_state.services = data['services']

    # set target_company variable to the first word of the filename separated by underscore and add it to the session state
    st.session_state.target_company = file_name.split('_')[0]
else:
    st.session_state.services = []
    st.session_state.target_company = "Unknown"

# Load the common CSS
load_css("pages/common.css")

def count_json_files(folder_name):
    path = os.path.join(os.path.dirname(__file__), '..', 'assets', folder_name)
    return len([f for f in os.listdir(path) if f.endswith('.json')])

# Count files in each Cosmos folder for Swiss roadside assistance
folders = {
    'customer': 'Cosmos_Customer',
    'vehicle': 'Cosmos_Vehicles',
    'assistance_case': 'Cosmos_AssistanceCases',
    'human_conversation': 'Cosmos_HumanConversations'
}

counts = {k: count_json_files(v) for k, v in folders.items()}

# Assign counts to variables for backward compatibility
customer_count = counts['customer']
vehicle_count = counts['vehicle']
assistance_case_count = counts['assistance_case']
human_conversation_count = counts['human_conversation']

col1, col2, col3, col4 = st.columns([3, 6, 6, 2])
with col1:
    st.write("The synthesized services are:")
    for service in st.session_state.services:
        st.markdown(f"- **{service}**",)
with col2:
    st.write(f"Current Company for synthesization: **{st.session_state.target_company}**")
    st.write(f"Number of customers synthesized: **{customer_count}**")
    st.write(f"Number of vehicles synthesized: **{vehicle_count}**")
    st.write(f"Number of assistance cases synthesized: **{assistance_case_count}**")
    st.write(f"Number of human conversations synthesized: **{human_conversation_count}**")
    st.markdown("---")
with col3:
    st.write("Enter the new company name for synthesization:")
    st.write("")
    st.write("Enter the number of customers to synthesize:")
    st.write("")
    st.write("Enter the number of services to synthesize:")
    st.write("")
    st.write("Enter the number of human conversations to synthesize:")
with col4:
    new_company = st.text_input("new company", key="new_company", label_visibility = "collapsed")  
    number_customer = st.text_input("number customer", key="number_customer", label_visibility = "collapsed")
    number_service = st.text_input("number service", key="number_service", label_visibility = "collapsed")
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
            "number_of_services": int(number_service),
            "number_of_human_conversations": int(number_human_conversation)
        }
        original_print(f"Parameters: {params}")
        run_synthesis(
            company_name=params["company_name"],
            num_customers=params["number_of_customers"],
            num_service_types=params["number_of_services"],
            num_conversations=params["number_of_human_conversations"]
        )
    finally:
        builtins.print = original_print
