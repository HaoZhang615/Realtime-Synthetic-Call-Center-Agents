#!/usr/bin/env python3
"""
Simple test script to verify Logic App email functionality.
This script tests the user_logic_apps.py utility independently.
"""

from collections.abc import Set
import os
import sys
from typing import Set

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ToolSet, FunctionTool
import logging
from azure.identity import DefaultAzureCredential

# Add the utils directory to the path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from utils import load_dotenv_from_azd
from utils.user_logic_apps import AzureLogicAppTool, create_send_email_function

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Suppress verbose Azure SDK logging
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.identity').setLevel(logging.WARNING)
logging.getLogger('azure.core').setLevel(logging.WARNING)
logging.getLogger('azure.mgmt').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load environment variables
logger.info("Loading environment variables from azd...")
load_dotenv_from_azd()
# Create the agents client
project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

def main():
    """Main test function."""
    try:
        
        # Get required environment variables
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
        resource_group = os.environ.get("AZURE_RESOURCE_GROUP")
        logic_app_name = os.environ.get("SEND_EMAIL_LOGIC_APP_NAME")
        trigger_name = os.environ.get("SEND_EMAIL_LOGIC_APP_TRIGGER_NAME", "When_a_HTTP_request_is_received")
        
        logger.info(f"Subscription ID: {subscription_id}")
        logger.info(f"Resource Group: {resource_group}")
        logger.info(f"Logic App Name: {logic_app_name}")
        logger.info(f"Trigger Name: {trigger_name}")
        
        # Check if required variables are available
        if not subscription_id:
            logger.error("AZURE_SUBSCRIPTION_ID environment variable is not set")
            return False
            
        if not resource_group:
            logger.error("AZURE_RESOURCE_GROUP environment variable is not set")
            return False
            
        if not logic_app_name:
            logger.error("SEND_EMAIL_LOGIC_APP_NAME environment variable is not set")
            return False
        
        # Test Azure authentication
        logger.info("Testing Azure authentication...")
        credential = DefaultAzureCredential()
        
        # Create AzureLogicAppTool instance
        logger.info("Creating AzureLogicAppTool instance...")
        logic_app_tool = AzureLogicAppTool(subscription_id, resource_group, credential)
        
        # Register the Logic App
        logger.info(f"Registering Logic App '{logic_app_name}' with trigger '{trigger_name}'...")
        logic_app_tool.register_logic_app(logic_app_name, trigger_name)
        logger.info("Logic App registered successfully!")
        
        # Create the send email function
        logger.info("Creating send email function...")
        send_email_func = create_send_email_function(logic_app_tool, logic_app_name)
        
        # Prepare the function tools for the agent
        functions_to_use: Set = {
            send_email_func,  # This references the AzureLogicAppTool instance via closure
        }
        # Test the send email function with dummy data
        logger.info("Testing send email function with test data...")
        test_recipient = "test@example.com"
        test_subject = "Test Email from Logic App"
        test_body = "This is a test email to verify Logic App functionality."
        
        with project_client:
            agents_client = project_client.agents

            # Create an agent
            functions = FunctionTool(functions=functions_to_use)
            toolset = ToolSet()
            toolset.add(functions)

            agents_client.enable_auto_function_calls(toolset)
            agent = agents_client.create_agent(
                model=os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"],
                name="SendEmailAgent",
                instructions="You are a specialized agent for sending emails.",
                toolset=toolset,
            )
            print(f"Created agent, ID: {agent.id}")

            # Create a thread for communication
            thread = agents_client.threads.create()
            print(f"Created thread, ID: {thread.id}")

            # Create a message in the thread
            message = agents_client.messages.create(
                thread_id=thread.id,
                role="user",
                content="Hello, please send an email to hao.zhang@microsoft.com just to say 'you are awesome!'",
            )
            print(f"Created message, ID: {message.id}")
            
            # Create and process an agent run in the thread
            run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
            print(f"Run finished with status: {run.status}")

            if run.status == "failed":
                print(f"Run failed: {run.last_error}")

            # Fetch and log all messages
            messages = agents_client.messages.list(thread_id=thread.id)
            for msg in messages:
                if msg.text_messages:
                    last_text = msg.text_messages[-1]
                    print(f"{msg.role}: {last_text.text.value}")
    #     result = send_email_func(test_recipient, test_subject, test_body)
    #     logger.info(f"Send email result: {result}")
        
        logger.info("✅ Logic App test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during Logic App test: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n💥 Test failed!")
        sys.exit(1)
