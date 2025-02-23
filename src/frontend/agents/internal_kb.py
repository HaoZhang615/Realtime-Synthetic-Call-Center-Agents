
import os
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
credential = DefaultAzureCredential() if key is None or key == "" else AzureKeyCredential(key)
search_client = SearchClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name=os.getenv("AZURE_SEARCH_INDEX"),
    credential=credential
)

async def query_internal_knowledge_base(params):
    query = params["query"]
    vector_query = VectorizableTextQuery(text=query, k_nearest_neighbors=3, fields="text_vector", exhaustive=True)
    search_results = search_client.search(
		search_text=query,  
		vector_queries= [vector_query],
		select=["title", "chunk_id", "chunk"],
		top=3
	)

	# Chunk id has format {parent_id}_pages_{page_number}
    sources_formatted = "\n".join([f'# Source "{document["title"]}" - Page {document["chunk_id"].split("_")[-1]}\n{document["chunk"]}' for document in search_results])
    
    return sources_formatted

internal_kb_agent = {
	"id": "Assistant_internal_kb_agent",
	"name": "Internal Knowledgebase Agent",
	"description": """Call this if:
		- You need to provide information about internal knowledge base.
		- You need to provide the user with the information they need to retrieve from the internal knowledge base.
		- You need to access the knowledge base to look up the answer to the user's question.""",
	"system_message": """
	You are an internal knowledge base assistant that responds to inquiries about the company's internal knowledge.
	You are responsible for providing the user with the information they need to retrieve from the internal knowledge base.
	
	Your tasks are:
	- Provide the user with the information they need to retrieve from the internal knowledge base.
	- Use the "query_internal_knowledge_base" tool to look up the solution to the user's issue.
	
	Make sure to act politely and professionally.""",
	"tools": [
		{
			"name": "query_internal_knowledge_base",
			"description": "Query the internal knowledge base for the solution to the user's issue.",
			"parameters": {
				"type": "object",
				"properties": {
					"query": {"type": "string", "description": "The user's query to look up in the internal knowledge base."},
				},
			},
			"returns": query_internal_knowledge_base,
		}
	],
}