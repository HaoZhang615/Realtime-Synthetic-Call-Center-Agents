import json
import os
import uuid
import random
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from datetime import datetime, timedelta, timezone
from utils import load_dotenv_from_azd


load_dotenv_from_azd()
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
# Constants for synthesis
MACHINE_TYPES = ['Lathe', 'Milling Machine', 'Drill Press', 'Laser Cutter', 'CNC Router', 'Injection Molding', 'Grinder', 'Punching Machine']
OPERATION_TYPES = ['Cutting', 'Drilling', 'Milling', 'Grinding', 'Engraving', 'Assembly', 'Inspection', 'Maintenance']
MACHINE_STATUS = ['Running', 'Idle', 'Maintenance', 'Error', 'Offline']
OPERATION_STATUS = ['Completed', 'In Progress', 'Scheduled', 'Paused', 'Failed']
SHIFTS = ['Morning', 'Afternoon', 'Night']
ROLES = ['Machine Operator', 'Senior Technician', 'Supervisor', 'Maintenance Engineer', 'Quality Control']
LOCATIONS = ['Section A', 'Section B', 'Section C', 'Section D', 'Section E', 'Assembly Line 1', 'Assembly Line 2', 'Finishing Area']
FIRST_NAME_LIST = ['Alex','Brian','Chloe','David','Emma','Fiona','George','Hannah','Ian','Julia','Kevin','Lucy','Michael',
    'Nicole','Oliver','Paula','Quinn','Rachel','Samuel','Tara','Ursula','Victor','Wendy','Xander','Yvonne','Zachary']
LAST_NAME_LIST = ["Anderson", "Brown", "Clark", "Davis", "Evans", "Foster", "Garcia", "Harris", "Ingram", "Johnson", "King", 
                  "Lewis", "Martin", "Nelson", "Owens", "Parker", "Quinn", "Robinson", "Smith", "Taylor", "Underwood", 
                  "Vargas", "Wilson", "Xavier", "Young", "Zimmerman"]

cosmos_machine_container_name = "Machine"
cosmos_operations_container_name = "Operations"
cosmos_operator_container_name = "Operator"

class DataSynthesizer:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.setup_azure_clients()
        self.setup_cosmos_containers()

    def setup_azure_clients(self):
        self.aoai_client = AzureOpenAI(
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
        )
        
        self.cosmos_client = CosmosClient(
            os.environ["COSMOSDB_ENDPOINT"], 
            DefaultAzureCredential()
        )
        self.database = self.cosmos_client.get_database_client(os.environ["COSMOSDB_DATABASE"])
    
    def setup_cosmos_containers(self):
        self.containers = {
            'machine': self.database.get_container_client(cosmos_machine_container_name),
            'operations': self.database.get_container_client(cosmos_operations_container_name),
            'operator': self.database.get_container_client(cosmos_operator_container_name),
        }

    def container_exists(self, database, container_name):
        try:
            container = database.get_container_client(container_name)
            # Attempt to read container properties to confirm existence
            container.read()
            return True, container
        except exceptions.CosmosResourceNotFoundError:
            return False, None

    # Function to get the partition key path from the container
    def get_partition_key_path(self, container):
        container_properties = container.read()
        return container_properties['partitionKey']['paths'][0]  
    
    def delete_all_items(self, container):
        query = "SELECT * FROM c"
        items = container.query_items(query, enable_cross_partition_query=True)
        
        for item in items:
            # Extract the partition key value from the document
            partition_key_value = item.get(self.get_partition_key_path(container).strip('/'))
            container.delete_item(item, partition_key=partition_key_value)
        print(f"All items in container '{container.id}' have been deleted.")

    def refresh_container(self, database, container_name, partition_key_path):
        exists, container = self.container_exists(database, container_name)
        
        if exists:
            print(f"Container '{container_name}' already exists. Deleting all items...")
            self.delete_all_items(container)
        else:
            print(f"Container '{container_name}' does not exist. Creating new container...")
            container = database.create_container(
                id=container_name, 
                partition_key=PartitionKey(path=partition_key_path),
                # offer_throughput=400
            )
            print(f"Container '{container_name}' has been created.")
        
        return container

    def save_json_files_to_cosmos_db(self, directory, container):
        for filename in os.listdir(directory):
            if not filename.endswith('.json'):
                continue
                
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            partition_key_path = container.read()['partitionKey']['paths'][0].strip('/')
            partition_key_value = data.get(partition_key_path)
            
            if partition_key_value:
                try:
                    container.upsert_item(body=data)
                    print(f"Document {filename} has been successfully created in Azure Cosmos DB!")
                except Exception as e:
                    print(f"Error uploading {filename}: {str(e)}")

    # delete all json files in the assets folder recursively
    def delete_json_files(self, base_dir):
        assets_dir = os.path.join(base_dir)
        # Walk through the directory and delete JSON files
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")  # Optional: Print out deleted file paths for confirmation

    def synthesize_everything(self, company_name, num_machines, num_operators, num_operations):
        
        # Refresh Cosmos DB containers
        self.refresh_container(self.database, cosmos_machine_container_name, "/MachineID")
        self.refresh_container(self.database, cosmos_operations_container_name, "/OperationID")
        self.refresh_container(self.database, cosmos_operator_container_name, "/OperatorID")
        
        # Delete all JSON files in the assets folder
        self.delete_json_files(self.base_dir)
        
        # Generate all data types
        self.synthesize_machines(num_machines)
        self.synthesize_operators(num_operators)
        self.synthesize_operations(num_operations)

        # Upload all data to Cosmos DB
        for folder, container in [
            ('Cosmos_Machine', self.containers['machine']),
            ('Cosmos_Operator', self.containers['operator']),
            ('Cosmos_Operations', self.containers['operations']),
        ]:
            self.save_json_files_to_cosmos_db(os.path.join(self.base_dir, folder), container)
        print("Data synthesis completed successfully!")

    def synthesize_machines(self, num_machines):
        machines = []
        
        for i in range(num_machines):
            machine_type = random.choice(MACHINE_TYPES)
            machine = {
                "MachineID": i + 1,
                "MachineName": f"{machine_type} {random.randint(1000, 9999)}",
                "MachineType": machine_type,
                "Location": random.choice(LOCATIONS),
                "Status": random.choice(MACHINE_STATUS),
                "id": f"machine_{i + 1}"
            }
            machines.append(machine)
            
            # Save each machine to a JSON file
            filename = f"{i}_{machine['MachineName'].replace(' ', '_')}.json"
            file_path = os.path.join(self.base_dir, "Cosmos_Machine", filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(machine, f, ensure_ascii=False, indent=4)
            print(f"Machine {filename} has been successfully created!")
        
        return machines

    def synthesize_operators(self, num_operators):
        operators = []
        
        for i in range(num_operators):
            first_name = random.choice(FIRST_NAME_LIST)
            last_name = random.choice(LAST_NAME_LIST)
            operator = {
                "OperatorID": 201 + i,
                "OperatorName": f"{first_name} {last_name}",
                "Shift": random.choice(SHIFTS),
                "Role": random.choice(ROLES),
                "id": f"operator_{201 + i}"
            }
            operators.append(operator)
            
            # Save each operator to a JSON file
            filename = f"{i}_{first_name}_{last_name}.json"
            file_path = os.path.join(self.base_dir, "Cosmos_Operator", filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(operator, f, ensure_ascii=False, indent=4)
            print(f"Operator {filename} has been successfully created!")
        
        return operators

    def synthesize_operations(self, num_operations):
        # Get the list of machine IDs and operator IDs we've created
        machine_ids = []
        operator_ids = []
        
        machine_directory = os.path.join(self.base_dir, "Cosmos_Machine")
        for filename in os.listdir(machine_directory):
            file_path = os.path.join(machine_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                machine = json.load(f)
                machine_ids.append(machine["MachineID"])
        
        operator_directory = os.path.join(self.base_dir, "Cosmos_Operator")
        for filename in os.listdir(operator_directory):
            file_path = os.path.join(operator_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                operator = json.load(f)
                operator_ids.append(operator["OperatorID"])
        
        operations = []
        
        # Generate random start dates in the last 30 days
        now = datetime.now(timezone.utc)
        
        for i in range(num_operations):
            # Randomly choose a machine and operator
            machine_id = random.choice(machine_ids) if machine_ids else 1
            operator_id = random.choice(operator_ids) if operator_ids else 201
            
            # Random start time in the last 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            start_time = (now - timedelta(days=days_ago, hours=hours_ago)).isoformat()
            
            # Determine if operation is completed
            status = random.choice(OPERATION_STATUS)
            operation_type = random.choice(OPERATION_TYPES)
            
            # If completed, set end time and output quantity
            end_time = None
            output_quantity = 0
            
            if status == "Completed":
                duration_hours = random.uniform(0.5, 4.0)  # Operation lasted 0.5 to 4 hours
                end_time = (now - timedelta(days=days_ago, hours=hours_ago - duration_hours)).isoformat()
                output_quantity = random.randint(50, 500)
            elif status == "In Progress":
                output_quantity = random.randint(0, 50)
            
            operation = {
                "OperationID": 100 + i,
                "MachineID": machine_id,
                "StartTime": start_time,
                "EndTime": end_time,
                "OperationType": operation_type,
                "OperatorID": operator_id,
                "Status": status,
                "OutputQuantity": output_quantity,
                "id": f"operation_{100 + i}"
            }
            operations.append(operation)
            
            # Save each operation to a JSON file
            filename = f"{i}_{operation_type}_{status}.json"
            file_path = os.path.join(self.base_dir, "Cosmos_Operations", filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(operation, f, ensure_ascii=False, indent=4)
            print(f"Operation {filename} has been successfully created!")
        
        return operations


def run_synthesis(company_name, num_machines, num_operators, num_operations):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    # Ensure the assets directory structure exists
    base_assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    for dir_name in ['Cosmos_Machine', 'Cosmos_Operations', 'Cosmos_Operator']:
        os.makedirs(os.path.join(base_assets_dir, dir_name), exist_ok=True)
    # print(f"Base directory: {base_dir}")
    synthesizer = DataSynthesizer(base_dir)
    synthesizer.synthesize_everything(company_name, num_machines, num_operators, num_operations)
