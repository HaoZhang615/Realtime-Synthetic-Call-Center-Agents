import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
import os
import aiohttp
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
import util
import logging

util.load_dotenv_from_azd()

# Bing Search Configuration
bing_api_key = os.getenv("BING_SEARCH_API_KEY")
has_bing_api_key = bing_api_key is not None and bing_api_key != ''

bing_api_endpoint = os.getenv("BING_SEARCH_API_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")

# CosmosDB Configuration
credential = DefaultAzureCredential()
cosmos_endpoint = os.getenv("COSMOSDB_ENDPOINT")
cosmos_client = CosmosClient(cosmos_endpoint, credential)
database_name = os.getenv("COSMOSDB_DATABASE")
database = cosmos_client.create_database_if_not_exists(id=database_name)
product_container_name = "Product"
producturl_container = database.get_container_client(os.getenv("COSMOSDB_ProductUrl_CONTAINER"))

def get_target_company():
    # use the first item in the Product container and get the value of the field "company"
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(product_container_name)
    try:
        # Query the container for the first item
        items = list(container.read_all_items())
        if items:
            return items[0]["company"]
        else:
            return None
    except exceptions.CosmosResourceNotFoundError as e:
        logging.error(f"CosmosHttpResponseError: {e}")
        return None
    
async def search_web(params):
    if not has_bing_api_key:
        return "Web search is currently unavailable because no Bing Search API key was provided."
        
    query = params["query"]
    up_to_date = params.get("up_to_date", False)

    try:
        # Retrieve the single ProductUrl document from CosmosDB
        items = list(producturl_container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))
        if items:
            restricted_urls = items[0].get('urls', [])
            if restricted_urls:
                concatenated_url_string = " OR ".join(
                    f"site:{url.replace('https://','').replace('http://','')}" for url in restricted_urls
                )
                query = f"{query} {concatenated_url_string}"
    except Exception as ex:
        logger.error(f"Error querying ProductUrl container: {ex}")

    headers = {"Ocp-Apim-Subscription-Key": bing_api_key}
    params = {"q": query, "count": 3}
    url = bing_api_endpoint
    if up_to_date:
        params.update({"sortby": "Date"})
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                search_results = await response.json()
                results = []
                if search_results and "webPages" in search_results and "value" in search_results["webPages"]:
                    for v in search_results["webPages"]["value"]:
                        result = {
                            "source_title": v["name"],
                            "content": v["snippet"],
                            "source_url": v["url"]
                        }
                        results.append(result)
                formatted_result = "\n".join([
                    f'{i}. content: {item["content"]}, source_title: {item["source_title"]}, source_url: {item["source_url"]}' 
                    for i, item in enumerate(results, 1)
                ])
                return formatted_result
    except Exception as ex:
        raise ex

web_search_agent = {
    "id": "Assistant_WebSearch",
    "name": "Web Search Agent",
    "description": """Call this if you need to retrieve up-to-date information from the web or if the user asks for web search specifically.""",
    "system_message": f"""
    You are a web search agent that queries Bing search engine to retrieve up-to-date information from the Internet.
    If user is asking about any related products or services from {get_target_company()}'s competitors or from the same industry, you promote {get_target_company()}'s equivalent products by directing to the Assistant_WebSearch to search the same category across {get_target_company()}'s portfolio.
    Your tasks are:
    - Use the 'search_web' tool to look up the web to find the solution to the user's issue directly, or search web to help as part of the whole solution.
    - Act politely and professionally. If the source is a famous and credible website, you can mention it to the user e.g. 'according to <source>'.
    """,
    "tools": [
        {
            "name": "search_web",
            "description": "Search Bing for relevant web information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "the rephrased user request considering the conversation history, in concise search terms that works efficiently in Bing Search.",
                    },
                    "up_to_date": {
                        "type": "boolean",
                        "default": False,
                        "description": "indicator of whether or not the up-to-date information is needed.",
                    }
                }
            },
            "returns": search_web,
        }
    ],
}