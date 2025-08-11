import os
from azure.ai.evaluation import TaskAdherenceEvaluator
from pprint import pprint

model_config = {
    "azure_endpoint": "https://<servicename>.openai.azure.com/",  # https://<account_name>.services.ai.azure.com
    "api_key": "<api_key>",
    "azure_deployment": "gpt-4o-mini",
}

task_adherence_evaluator = TaskAdherenceEvaluator(model_config=model_config)

query = [
    {"role": "system", "content": "You are a helpful customer service agent."},
    {"role": "user", "content": [{"type": "text", "text": "What is the status of my order #123?"}]},
]

response = [
    {
        "role": "assistant",
        "content": [
            {
                "type": "tool_call",
                "tool_call": {
                    "id": "tool_001",
                    "type": "function",
                    "function": {"name": "get_order", "arguments": {"order_id": "123"}},
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "tool_001",
        "content": [
            {"type": "tool_result", "tool_result": '{ "order": { "id": "123", "status": "shipped" } }'}
        ],
    },
    {"role": "assistant", "content": [{"type": "text", "text": "Your order #123 has been shipped."}]},
]

tool_definitions = [
    {
        "name": "get_order",
        "description": "Get order details.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}},
    }
]

result = task_adherence_evaluator(query=query, response=response, tool_definitions=tool_definitions)

print("Task Adherence Evaluation Result:")
pprint(result)