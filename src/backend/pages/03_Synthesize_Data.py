import streamlit as st
import os
import sys
import json
import logging
from azure.identity import DefaultAzureCredential
from utils.data_synthesizer import run_synthesis

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
logger = logging.getLogger(__name__)

# Ensure the assets directory structure exists
base_assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
for dir_name in ['Cosmos_Machine', 'Cosmos_Operations', 'Cosmos_Operator']:
    os.makedirs(os.path.join(base_assets_dir, dir_name), exist_ok=True)

st.set_page_config(
    page_title="Synthesize Data",
    page_icon=":factory:",
    layout="wide",
    menu_items=None,
)

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load the common CSS
load_css("pages/common.css")

def count_json_files(folder_name):
    path = os.path.join(os.path.dirname(__file__), '..', 'assets', folder_name)
    return len([f for f in os.listdir(path) if f.endswith('.json')])

# Count files in each Cosmos folder
folders = {
    'machine': 'Cosmos_Machine',
    'operations': 'Cosmos_Operations',
    'operator': 'Cosmos_Operator'
}

counts = {k: count_json_files(v) for k, v in folders.items()}

# Assign counts to variables
machine_count = counts['machine']
operations_count = counts['operations']
operator_count = counts['operator']

st.write("# Manufacturing Operations Data Synthesis")

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    st.markdown("### Current Data Statistics")
    st.write(f"Number of machines synthesized: **{machine_count}**")
    st.write(f"Number of operators synthesized: **{operator_count}**")
    st.write(f"Number of operations synthesized: **{operations_count}**")
    st.markdown("---")

with col2:
    st.markdown("### Manufacturing Data Schema")
    st.markdown("""
    **Machine**
    ```json
    {
      "MachineID": 1,
      "MachineName": "CNC Lathe 5000",
      "MachineType": "Lathe",
      "Location": "Section A",
      "Status": "Running"
    }
    ```
    
    **Operations**
    ```json
    {
      "OperationID": 101,
      "MachineID": 1,
      "StartTime": "2025-03-03T08:00:00Z",
      "EndTime": "2025-03-03T10:30:00Z",
      "OperationType": "Cutting",
      "OperatorID": 201,
      "Status": "Completed",
      "OutputQuantity": 150
    }
    ```
    
    **Operators**
    ```json
    {
      "OperatorID": 201,
      "OperatorName": "Alice Johnson",
      "Shift": "Morning",
      "Role": "Machine Operator"
    }
    ```
    """)

with col3:
    st.markdown("### Generate New Data")
    st.write("Enter the number of machines to synthesize:")
    num_machines = st.number_input("Number of machines", min_value=1, max_value=100, value=10, step=1, key="num_machines", label_visibility="collapsed")
    
    st.write("Enter the number of operators to synthesize:")
    num_operators = st.number_input("Number of operators", min_value=1, max_value=100, value=5, step=1, key="num_operators", label_visibility="collapsed")
    
    st.write("Enter the number of operations to synthesize:")
    num_operations = st.number_input("Number of operations", min_value=1, max_value=200, value=20, step=1, key="num_operations", label_visibility="collapsed")
    
    st.write("Enter the company name for the simulation:")
    company_name = st.text_input("Company name", value="ManufacturingCorp", key="company_name", label_visibility="collapsed")
        
# Move the log placeholder outside of the column layout
log_placeholder = st.empty()
logs = []

# execute the synthesization process by clicking the button
if st.button("Synthesize Data"):
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
            "company_name": company_name,
            "num_machines": int(num_machines),
            "num_operators": int(num_operators),
            "num_operations": int(num_operations)
        }
        original_print(f"Parameters: {params}")
        run_synthesis(
            company_name=params["company_name"],
            num_machines=params["num_machines"],
            num_operators=params["num_operators"],
            num_operations=params["num_operations"]
        )
    finally:
        builtins.print = original_print
