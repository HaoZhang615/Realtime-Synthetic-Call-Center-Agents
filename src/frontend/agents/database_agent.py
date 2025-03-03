import os
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
import util
from typing import Dict, List, Optional, Union
import logging
import uuid
from datetime import datetime, timezone, timedelta

util.load_dotenv_from_azd()

# CosmosDB Configuration
credential = DefaultAzureCredential()
cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
cosmos_client = CosmosClient(cosmos_endpoint, credential)
database_name = os.getenv("COSMOSDB_DATABASE")
database = cosmos_client.create_database_if_not_exists(id=database_name)
machine_container_name = "Machine"
operations_container_name = "Operations"
operator_container_name = "Operator"

class DatabaseAgent:
    def __init__(self, machine_id: str = None, operator_id: str = None):
        self.machine_id = machine_id
        self.operator_id = operator_id

    def validate_machine_exists(self, container) -> bool:
        """Validates if a machine exists in the database."""
        if not self.machine_id:
            return False
            
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.MachineID = @machine_id"
        parameters = [{"name": "@machine_id", "value": int(self.machine_id)}]
        result = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return result[0] > 0 if result else False
        
    def validate_operator_exists(self, container) -> bool:
        """Validates if an operator exists in the database."""
        if not self.operator_id:
            return False
            
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.OperatorID = @operator_id"
        parameters = [{"name": "@operator_id", "value": int(self.operator_id)}]
        result = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return result[0] > 0 if result else False

    def create_operation_record(self, parameters: Dict) -> str:
        """Creates a new operation record in the Operations container."""
        operation_record = parameters.get('operation_record', {})
        
        # Check for required fields
        if "MachineID" not in operation_record:
            if self.machine_id:
                operation_record["MachineID"] = int(self.machine_id)
            else:
                return "Missing required field: MachineID"
                
        if "OperatorID" not in operation_record:
            if self.operator_id:
                operation_record["OperatorID"] = int(self.operator_id)
            else:
                return "Missing required field: OperatorID" 
                
        container = database.get_container_client(operations_container_name)
        machine_container = database.get_container_client(machine_container_name)
        operator_container = database.get_container_client(operator_container_name)
        
        # Validate machine exists
        if not self.validate_machine_exists(machine_container):
            return f"Machine with ID {operation_record['MachineID']} not found"
        
        # Validate operator exists
        if not self.validate_operator_exists(operator_container):
            return f"Operator with ID {operation_record['OperatorID']} not found"
        
        # Create operation ID if not provided
        if "OperationID" not in operation_record:
            # Find the max operation ID and increment by 1
            query = "SELECT VALUE MAX(c.OperationID) FROM c"
            max_id_result = list(container.query_items(query=query, enable_cross_partition_query=True))
            next_id = 100
            if max_id_result and max_id_result[0] is not None:
                next_id = max_id_result[0] + 1
            operation_record["OperationID"] = next_id
            
        # Set default values for other fields if not provided
        if "StartTime" not in operation_record:
            operation_record["StartTime"] = datetime.now(timezone.utc).isoformat()
        
        if "Status" not in operation_record:
            operation_record["Status"] = "In Progress"
            
        if "OperationType" not in operation_record:
            operation_record["OperationType"] = "Unknown"
            
        if "OutputQuantity" not in operation_record:
            operation_record["OutputQuantity"] = 0
        
        # Create final record
        final_record = {
            "OperationID": operation_record["OperationID"],
            "MachineID": operation_record["MachineID"],
            "StartTime": operation_record["StartTime"],
            "EndTime": operation_record.get("EndTime"),
            "OperationType": operation_record["OperationType"],
            "OperatorID": operation_record["OperatorID"],
            "Status": operation_record["Status"],
            "OutputQuantity": operation_record["OutputQuantity"],
            "id": f"operation_{operation_record['OperationID']}"
        }
        
        try:
            container.create_item(body=final_record)
            return "Operation record created successfully."
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to create operation record: {e}")
            return f"Failed to create operation record: {str(e)}"

    def update_machine_record(self, parameters: Dict) -> str:
        """Updates an existing machine record in the Machine container."""
        if not self.machine_id:
            return "Machine ID is required for update operations"
            
        container = database.get_container_client(machine_container_name)

        # Query to find the machine document using MachineID
        query = f"SELECT * FROM c WHERE c.MachineID = {int(self.machine_id)}"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        if not items:
            return f"Machine with ID {self.machine_id} not found"
        
        machine_doc = items[0]
        
        # Extract only updatable fields from parameters
        updatable_fields = ['MachineName', 'MachineType', 'Location', 'Status']
        update_data = {k: v for k, v in parameters.items() if k in updatable_fields}
        
        # Update the document with allowed fields only
        machine_doc.update(update_data)
        
        # Replace the item
        try:
            container.replace_item(
                item=machine_doc,
                body=machine_doc
            )
            return {"status": "success", "message": "Machine record updated successfully"}
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to update machine record: {e}")
            return f"Failed to update machine record: {str(e)}"

    def update_operator_record(self, parameters: Dict) -> str:
        """Updates an existing operator record in the Operator container."""
        if not self.operator_id:
            return "Operator ID is required for update operations"
            
        container = database.get_container_client(operator_container_name)

        # Query to find the operator document using OperatorID
        query = f"SELECT * FROM c WHERE c.OperatorID = {int(self.operator_id)}"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        if not items:
            return f"Operator with ID {self.operator_id} not found"
        
        operator_doc = items[0]
        
        # Extract only updatable fields from parameters
        updatable_fields = ['OperatorName', 'Shift', 'Role']
        update_data = {k: v for k, v in parameters.items() if k in updatable_fields}
        
        # Update the document with allowed fields only
        operator_doc.update(update_data)
        
        # Replace the item
        try:
            container.replace_item(
                item=operator_doc,
                body=operator_doc
            )
            return {"status": "success", "message": "Operator record updated successfully"}
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to update operator record: {e}")
            return f"Failed to update operator record: {str(e)}"

    def get_machine_record(self, parameters: Dict) -> Union[Dict, str]:
        """Retrieves machine information from the Machine container."""
        container = database.get_container_client(machine_container_name)
        try:
            if "MachineID" in parameters:
                machine_id = int(parameters["MachineID"])
                query = """SELECT 
                    c.MachineID,
                    c.MachineName,
                    c.MachineType,
                    c.Location,
                    c.Status
                FROM c 
                WHERE c.MachineID = @machine_id"""
                
                query_params = [{"name": "@machine_id", "value": machine_id}]
                items = list(container.query_items(
                    query=query,
                    parameters=query_params,
                    enable_cross_partition_query=True
                ))
                if not items:
                    return f"No machine found with ID: {machine_id}"
                return items[0]
            else:
                # Get all machines with limited fields
                query = """SELECT 
                    c.MachineID,
                    c.MachineName,
                    c.MachineType,
                    c.Location,
                    c.Status
                FROM c"""
                items = list(container.query_items(query=query, enable_cross_partition_query=True))
                return items if items else "No machines found."
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get machine record(s): {e}")
            return f"Failed to get machine record(s): {str(e)}"

    def get_operator_record(self, parameters: Dict) -> Union[Dict, str]:
        """Retrieves operator information from the Operator container."""
        container = database.get_container_client(operator_container_name)
        try:
            if "OperatorID" in parameters:
                operator_id = int(parameters["OperatorID"])
                query = """SELECT 
                    c.OperatorID,
                    c.OperatorName,
                    c.Shift,
                    c.Role
                FROM c 
                WHERE c.OperatorID = @operator_id"""
                
                query_params = [{"name": "@operator_id", "value": operator_id}]
                items = list(container.query_items(
                    query=query,
                    parameters=query_params,
                    enable_cross_partition_query=True
                ))
                if not items:
                    return f"No operator found with ID: {operator_id}"
                return items[0]
            else:
                # Get all operators with limited fields
                query = """SELECT 
                    c.OperatorID,
                    c.OperatorName,
                    c.Shift,
                    c.Role
                FROM c"""
                items = list(container.query_items(query=query, enable_cross_partition_query=True))
                return items if items else "No operators found."
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get operator record(s): {e}")
            return f"Failed to get operator record(s): {str(e)}"

    def get_operations_record(self, parameters: Dict) -> Union[List[Dict], str]:
        """Retrieves operations records with optional filtering."""
        operations_container = database.get_container_client(operations_container_name)
        
        try:
            # Build query with optional filters
            base_query = """SELECT 
                c.OperationID,
                c.MachineID,
                c.StartTime,
                c.EndTime,
                c.OperationType,
                c.OperatorID,
                c.Status,
                c.OutputQuantity
            FROM c"""
            
            query_filters = []
            query_params = []
            
            # Add filters based on parameters
            if self.machine_id:
                query_filters.append("c.MachineID = @machine_id")
                query_params.append({"name": "@machine_id", "value": int(self.machine_id)})
                
            if self.operator_id:
                query_filters.append("c.OperatorID = @operator_id")
                query_params.append({"name": "@operator_id", "value": int(self.operator_id)})
                
            if "status" in parameters:
                query_filters.append("c.Status = @status")
                query_params.append({"name": "@status", "value": parameters["status"]})
            
            # Combine the query
            if query_filters:
                query = f"{base_query} WHERE {' AND '.join(query_filters)}"
            else:
                query = base_query
            
            # Get operations
            operations = list(operations_container.query_items(
                query=query,
                parameters=query_params,
                enable_cross_partition_query=True
            ))

            if not operations:
                filter_desc = ""
                if self.machine_id:
                    filter_desc += f" for machine ID {self.machine_id}"
                if self.operator_id:
                    filter_desc += f" for operator ID {self.operator_id}" 
                if "status" in parameters:
                    filter_desc += f" with status {parameters['status']}"
                    
                return f"No operations found{filter_desc}."

            # Add machine and operator details
            return self.enhance_operation_records(operations)

        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Failed to get operations records: {e}")
            return f"Failed to get operations records: {str(e)}"
    
    def enhance_operation_records(self, operations):
        """Add machine and operator details to operation records."""
        machine_container = database.get_container_client(machine_container_name)
        operator_container = database.get_container_client(operator_container_name)
        
        # Get unique machine and operator IDs
        machine_ids = set(op["MachineID"] for op in operations)
        operator_ids = set(op["OperatorID"] for op in operations)
        
        # Get machine details
        machines = {}
        for machine_id in machine_ids:
            query = f"SELECT c.MachineName, c.MachineType FROM c WHERE c.MachineID = {machine_id}"
            machine_list = list(machine_container.query_items(query=query, enable_cross_partition_query=True))
            if machine_list:
                machines[machine_id] = machine_list[0]
        
        # Get operator details
        operators = {}
        for operator_id in operator_ids:
            query = f"SELECT c.OperatorName, c.Role FROM c WHERE c.OperatorID = {operator_id}"
            operator_list = list(operator_container.query_items(query=query, enable_cross_partition_query=True))
            if operator_list:
                operators[operator_id] = operator_list[0]
        
        # Enhance operations with machine and operator details
        enhanced_operations = []
        for operation in operations:
            machine_id = operation["MachineID"]
            operator_id = operation["OperatorID"]
            
            enhanced_op = operation.copy()
            
            if machine_id in machines:
                enhanced_op["Machine"] = {
                    "MachineName": machines[machine_id].get("MachineName", "Unknown"),
                    "MachineType": machines[machine_id].get("MachineType", "Unknown")
                }
            
            if operator_id in operators:
                enhanced_op["Operator"] = {
                    "OperatorName": operators[operator_id].get("OperatorName", "Unknown"),
                    "Role": operators[operator_id].get("Role", "Unknown")
                }
            
            enhanced_operations.append(enhanced_op)
        
        return enhanced_operations

def database_agent(machine_id: str = None, operator_id: str = None):
    """Creates and returns the database agent configuration with the given machine_id or operator_id."""
    agent = DatabaseAgent(machine_id, operator_id)
    
    return {
        "id": "Assistant_Database_Agent",
        "name": "Database Agent",
        "description": """This agent interacts with a database that contains 'Machine', 'Operations' and 'Operator' containers/tables. It provides specific tools for creating operations, updating machine/operator information, and retrieving records from all containers.""",
        "system_message": """
You are a database assistant that manages records for a manufacturing operations system in CosmosDB with specific operations for each container type. Use the provided tools to perform database operations.
Interaction goes over voice, so it's *super* important that answers are as short as possible. Use professional language.

Available operations:
- create_operation_record: creates a new operation record in the Operations container.
- update_machine_record: updates an existing machine record in the Machine container.
- update_operator_record: updates an existing operator record in the Operator container.
- get_machine_record: retrieves all machines or a specific machine from the Machine container.
- get_operator_record: retrieves all operators or a specific operator from the Operator container.
- get_operations_record: retrieves operations based on optional filters (machine_id, operator_id, status).

NOTES:
- Before updating or creating any records, make sure to confirm the details with the user.
- Operations are always associated with both a machine and an operator.
- Before creating or updating a record, use the 'get' tools to retrieve the required schema of the respective container.

IMPORTANT: Never invent new tool or function names. Always use only the provided tools when interacting with the database. You are not allowed to delete any records.
""",
        "tools": [
            {
                "name": "create_operation_record",
                "description": "Create a new operation record in the Operations container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation_record": {
                            "type": "object",
                            "description": "The operation record containing MachineID, OperatorID, OperationType, etc."
                        }
                    },
                    "required": ["operation_record"]
                },
                "returns": agent.create_operation_record
            },
            {
                "name": "update_machine_record",
                "description": "Update machine information in the Machine container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "MachineName": {"type": "string", "description": "Machine's name"},
                        "MachineType": {"type": "string", "description": "Type of machine"},
                        "Location": {"type": "string", "description": "Machine's location"},
                        "Status": {"type": "string", "description": "Current status of the machine"}
                    }
                },
                "returns": agent.update_machine_record
            },
            {
                "name": "update_operator_record",
                "description": "Update operator information in the Operator container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "OperatorName": {"type": "string", "description": "Operator's full name"},
                        "Shift": {"type": "string", "description": "Operator's shift (Morning, Afternoon, Night)"},
                        "Role": {"type": "string", "description": "Operator's role"}
                    }
                },
                "returns": agent.update_operator_record
            },
            {
                "name": "get_machine_record",
                "description": "Retrieve all machines or a specific machine from the Machine container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "MachineID": {"type": "string", "description": "Optional: The specific machine ID to look up"}
                    },
                    "required": []
                },
                "returns": agent.get_machine_record
            },
            {
                "name": "get_operator_record",
                "description": "Retrieve all operators or a specific operator from the Operator container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "OperatorID": {"type": "string", "description": "Optional: The specific operator ID to look up"}
                    },
                    "required": []
                },
                "returns": agent.get_operator_record
            },
            {
                "name": "get_operations_record",
                "description": "Retrieve operations with optional filtering by machine, operator, or status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Optional: Filter by operation status"}
                    },
                    "required": []
                },
                "returns": agent.get_operations_record
            }
        ]
    }
