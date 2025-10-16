import json
import os
import uuid
import random
import logging
import sys
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from datetime import datetime, timedelta
from utils import load_dotenv_from_azd

# Set up logger for data synthesizer
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Ensure logs go to stdout so they can be captured if stdout is redirected
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Avoid duplicate emission to root logger

load_dotenv_from_azd()
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
# Constants for synthesis
SENTIMENTS_LIST = ['positive', 'negative', 'neutral']
TOPICS_LIST = ['churn', 'assistance', 'support', 'information', 'billing', 'payment', 'account', 'service', 'Quality', 'Sustainability']
AGENT_LIST = ['adam','betrace','curie','davinci','emil', 'fred']
FIRST_NAME_LIST = ['Alex','Brian','Chloe','David','Emma','Fiona','George','Hannah','Ian','Julia','Kevin','Lucy','Michael',
    'Nicole','Oliver','Paula','Quinn','Rachel','Samuel','Tara','Ursula','Victor','Wendy','Xander','Yvonne','Zachary']
LAST_NAME_LIST = ["Anderson", "Brown", "Clark", "Davis", "Evans", "Foster", "Garcia", "Harris", "Ingram", "Johnson", "King", 
                  "Lewis", "Martin", "Nelson", "Owens", "Parker", "Quinn", "Robinson", "Smith", "Taylor", "Underwood", 
                  "Vargas", "Wilson", "Xavier", "Young", "Zimmerman"]

cosmos_customer_container_name = os.environ["COSMOSDB_Customer_CONTAINER"]
cosmos_product_container_name = os.environ["COSMOSDB_Product_CONTAINER"]
cosmos_purchases_container_name = os.environ["COSMOSDB_Purchases_CONTAINER"]
cosmos_ai_conversations_container_name = os.environ["COSMOSDB_AIConversations_CONTAINER"]
cosmos_human_conversations_container_name = os.environ["COSMOSDB_HumanConversations_CONTAINER"]
cosmos_producturl_container_name = os.environ["COSMOSDB_ProductUrl_CONTAINER"]

class DataSynthesizer:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.setup_azure_clients()
        self.setup_cosmos_containers()

    def setup_azure_clients(self):
        self.aoai_client = AzureOpenAI(
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
            azure_endpoint=os.environ["AZURE_AI_FOUNDRY_ENDPOINT"]
        )
        
        self.cosmos_client = CosmosClient(
            os.environ["COSMOSDB_ENDPOINT"], 
            DefaultAzureCredential()
        )
        self.database = self.cosmos_client.get_database_client(os.environ["COSMOSDB_DATABASE"])
    def setup_cosmos_containers(self):
        self.containers = {
            'customer': self.database.get_container_client(cosmos_customer_container_name),
            'product': self.database.get_container_client(cosmos_product_container_name),
            'purchases': self.database.get_container_client(cosmos_purchases_container_name),
            'human_conversations': self.database.get_container_client(cosmos_human_conversations_container_name),
            'product_url': self.database.get_container_client(cosmos_producturl_container_name),
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
        logger.info(f"All items in container '{container.id}' have been deleted.")

    def refresh_container(self, database, container_name, partition_key_path):
        exists, container = self.container_exists(database, container_name)
        
        if exists:
            logger.info(f"Container '{container_name}' already exists. Deleting all items...")
            self.delete_all_items(container)
        else:
            logger.info(f"Container '{container_name}' does not exist. Creating new container...")
            container = database.create_container(
                id=container_name, 
                partition_key=PartitionKey(path=partition_key_path),
                # offer_throughput=400
            )
            logger.info(f"Container '{container_name}' has been created.")
        
        return container
    def create_document(self, prompt, temperature=0.9, max_tokens=2000):
        response = self.aoai_client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_GPT_CHAT_DEPLOYMENT"],
            messages=[
                {"role": "system", "content": "You are a helpful assistant who helps people"},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    # function to create dynamic document name based on the randomized combination of sentiment, topic and product. 
    def create_document_name(self, i, random_selection1, random_selection2, random_selection3):
        # Create a name for the document based on the 3 randomly selected values.
        # if the product name has spaces, replace them with underscores
        document_name = f"{i}_{random_selection1.replace(' ', '_')}_{random_selection2.replace(' ', '_')}_{random_selection3.replace(' ', '_')}.json"
        return document_name

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
                    logger.info(f"Document {filename} has been successfully created in Azure Cosmos DB!")
                except Exception as e:
                    logger.error(f"Error uploading {filename}: {str(e)}")
    # delete all json files in the assets folder recursively
    def delete_json_files(self, base_dir):
        assets_dir = os.path.join(base_dir)
        # Walk through the directory and delete JSON files
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                    logger.info(f"Deleted: {file_path}")  # Optional: Log deleted file paths for confirmation

    def synthesize_everything(self, company_name, num_customers, num_products):
        
        # Refresh Cosmos DB containers
        self.refresh_container(self.database, cosmos_producturl_container_name, "/company_name")
        self.refresh_container(self.database, cosmos_customer_container_name, "/customer_id")
        self.refresh_container(self.database, cosmos_product_container_name, "/product_id")
        self.refresh_container(self.database, cosmos_purchases_container_name, "/customer_id")
        self.refresh_container(self.database, cosmos_human_conversations_container_name, "/customer_id")
        self.refresh_container(self.database, cosmos_ai_conversations_container_name, "/customer_id")
        
        # Delete all JSON files in the assets folder
        self.delete_json_files(self.base_dir)
        # Generate all data types
        self.create_product_and_url_list(company_name, num_products)
        self.synthesize_customer_profiles(num_customers)
        self.synthesize_product_profiles(company_name)
        self.synthesize_purchases()
        self.synthesize_human_conversations()

        # Upload all data to Cosmos DB
        for folder, container in [
            ('Cosmos_ProductUrl', self.containers['product_url']),
            ('Cosmos_Customer', self.containers['customer']),
            ('Cosmos_Product', self.containers['product']),
            ('Cosmos_Purchases', self.containers['purchases']),
            ('Cosmos_HumanConversations', self.containers['human_conversations'])
        ]:
            self.save_json_files_to_cosmos_db(os.path.join(self.base_dir, folder), container)
        logger.info("Data synthesis completed successfully!")

    def create_product_and_url_list(self, company_name, number_of_product):
        
        product_and_url_creation_prompt = f"""generate a json list of {number_of_product} most popular product at brand level of the company {company_name}, and the official website url of those products. 
                Example for microsoft: Xbox, Surface, Windows, Office, Azure. Example for apple: iPhone, iPad, Mac, Apple Watch, AirPods. Example for Unilever: Dove, Lipton, Hellmann's, Knorr, Ben & Jerry's.
                The list contains two keys: 'products' and 'urls'. The 'products' key contains the list of products and the 'urls' key contains the list of urls."""
        # Generate the document using Azure OpenAI
        generated_document = self.create_document(product_and_url_creation_prompt)
        # Parse the document and prepare it for CosmosDB
        data = json.loads(generated_document)
        enhanced_document = {
            'company_name': company_name,
            'id': f"{company_name}_products_and_urls",
            'products': data['products'],
            'urls': data['urls']
        }
        # Create a dynamic document name
        document_name = f"{company_name}_products_and_urls.json"
        
        # Save the enhanced document to the local folder
        file_path = os.path.join(self.base_dir, "Cosmos_ProductUrl", document_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_document, f, ensure_ascii=False, indent=4)    
            
        logger.info(f"Document {document_name} has been successfully created!")

    def synthesize_customer_profiles(self, num_customers):
        for i in range(num_customers):
            # Randomly select first and last names
            random_firstname = random.choice(FIRST_NAME_LIST)
            random_lastname = random.choice(LAST_NAME_LIST)
            
            # Create prompt for Azure OpenAI
            document_creation_prompt = f"""CREATE a JSON document of a customer profile whose first name is {random_firstname} and last name is {random_lastname}. 
            The required schema for the document is to follow the example below:
            {{
                "first_name": "Alex",
                "last_name": "Richardson",
                "email": "alex.richardson@example.com",
                "address": {{
                    "street": "Fourth St 19",
                    "city": "Chicago",
                    "postal_code": "60601",
                    "country": "USA"
                }},
                "phone_number": "+17845403125"
            }}
            Be creative about the values and do not use markdown to format the json object.
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = f"{i}_{random_firstname}_{random_lastname}.json"
            
            # Save the generated document to the local folder
            file_path = os.path.join(self.base_dir, "Cosmos_Customer", document_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            logger.info(f"Document {document_name} has been successfully created!")
        
        # Update the JSON files with customer_id and id fields
        directory = os.path.join(self.base_dir, "Cosmos_Customer")
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                customer_profile = json.load(f)
                customer_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{customer_profile['first_name']}_{customer_profile['last_name']}").hex
                customer_profile['customer_id'] = customer_id
                customer_profile['id'] = f"{filename.split('_')[0]}_{customer_id}"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(customer_profile, f, ensure_ascii=False, indent=4)
            logger.info(f"Document {filename} has been successfully updated!")

    def synthesize_product_profiles(self, company_name):
        producturls_file_path = os.path.join(self.base_dir, "Cosmos_ProductUrl", f"{company_name}_products_and_urls.json")
        with open(producturls_file_path, "r", encoding="utf-8") as f:
            products_list = json.load(f)["products"]
        for idx, product in enumerate(products_list):
            # Create prompt for Azure OpenAI
            document_creation_prompt = f"""CREATE a JSON document of a product profile. The product is {product} made by {company_name}. 
            The required schema for the document is to follow the example below:
            {{
                "name": "string", 
                "category": "string", 
                "type": "string", 
                "brand": "string", 
                "company": "string",
                "unit_price": "number",
                "weight": {{
                    "value": "number",
                    "unit": "string"
                }},
                "color": "string", 
                "material": "string"
            }}
            Be creative about the values and do not use markdown to format the json object. if any field is not applicable, leave it empty.
            the value of the key 'company' should always be: {company_name}.
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = f"{idx}_{product.replace(' ', '_')}.json"
            file_path = os.path.join(self.base_dir, "Cosmos_Product", document_name)
            
            # Save the generated document to the local folder
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            logger.info(f"Document {document_name} has been successfully created!")
        
        # Additional logic to update product profiles:
        # loop through the files in the local folder Cosmos_Product and update them:
        # 1. add a product_id field (hash value based on the current file name) to the content
        # 2. add a id field (hash value based on the prefix value of the current file name and the product_id) to the content
        # 3. save the updated content back to the file
        directory = os.path.join(self.base_dir, "Cosmos_Product")
        for filename in os.listdir(directory):
            path = os.path.join(directory, filename)
            with open(path, 'r', encoding='utf-8') as f:
                product_profile = json.load(f)
                product_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{filename}").hex
                product_profile['product_id'] = product_id
                product_profile['id'] = f"{filename.split('_')[0]}_{product_id}"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(product_profile, f, ensure_ascii=False, indent=4)
            logger.info(f"Document {filename} has been successfully updated!")

    def get_today_date(self):
        return datetime.today().strftime("%B %d, %Y")

    def get_product_profile(self, product_id):
        # Read the product file directly from the local directory instead of querying
        product_directory = os.path.join(self.base_dir, "Cosmos_Product")
        for filename in os.listdir(product_directory):
            file_path = os.path.join(product_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                product = json.load(f)
                if product.get('product_id') == product_id:
                    # Remove technical fields that shouldn't be in product_details
                    product_details = product.copy()
                    technical_fields = ['id', '_rid', '_self', '_etag', '_attachments', '_ts']
                    for field in technical_fields:
                        product_details.pop(field, None)
                    return product_details
        return {}

    def get_customer_name(self, customer_id):
        """Get customer's first name from their customer_id"""
        customer_directory = os.path.join(self.base_dir, "Cosmos_Customer")
        for filename in os.listdir(customer_directory):
            file_path = os.path.join(customer_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                customer = json.load(f)
                if customer.get('customer_id') == customer_id:
                    return customer.get('first_name', 'Customer')
        return 'Customer'  # Fallback

    def synthesize_purchases(self):
        # Loop through the files in Cosmos_Customer and Cosmos_Product to gather customer_ids and product_ids
        customer_ids = []
        product_ids = []
        customer_directory = os.path.join(self.base_dir, "Cosmos_Customer")
        for filename in os.listdir(customer_directory):
            file_path = os.path.join(customer_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                customer_profile = json.load(f)
                customer_ids.append(customer_profile.get('customer_id'))
        
        product_directory = os.path.join(self.base_dir, "Cosmos_Product")
        for filename in os.listdir(product_directory):
            file_path = os.path.join(product_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                product_profile = json.load(f)
                product_ids.append(product_profile.get('product_id'))
        
        # For each customer, generate 4 random purchase records with random product_id
        for idx, customer_id in enumerate(customer_ids):
            for i in range(4):
                random_product_id = random.choice(product_ids)
                document_creation_prompt = f"""CREATE a JSON document of a purchase record. The product_id is {random_product_id} which is bought by the customer_id {customer_id}. 
                The required schema for the document is to follow the example below:
                {{
                    "customer_id": "string",
                    "product_id": "string",
                    "quantity": "number",
                    "purchasing_date": "datetime",
                    "delivered_date": "datetime"
                }}
                Do not use markdown to format the json object. if any field is not applicable, leave it empty.
                quantity should be a random number between 1 and 10.
                Today is {self.get_today_date()}, the purchasing_date and delivered_date should be within the last 6 months of today's date.
                """

                generated_document = self.create_document(document_creation_prompt)
                document_name = self.create_document_name(idx*4+i+1, random_product_id, customer_id, "")

                # Save the JSON document to the local folder Cosmos_Purchases
                file_path = os.path.join(self.base_dir, "Cosmos_Purchases", document_name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(generated_document)
                logger.info(f"Document {document_name} has been successfully created!")
                # time.sleep(1)
        
        # Update the purchase records with additional fields
        purchases_directory = os.path.join(self.base_dir, "Cosmos_Purchases")
        for filename in os.listdir(purchases_directory):
            file_path = os.path.join(purchases_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                purchase = json.load(f)
                
                # Get product details for this purchase
                product_details = self.get_product_profile(purchase.get('product_id', ''))
                if not product_details:
                    logger.warning(f"Warning: No product details found for product_id: {purchase.get('product_id')} in {filename}")
                    
                # Update purchase record
                order_number = uuid.uuid3(uuid.NAMESPACE_DNS, f"{filename}").hex
                purchase['order_number'] = order_number
                purchase['product_details'] = product_details
                purchase['total_price'] = product_details.get('unit_price', 0) * purchase.get('quantity', 0)
                purchase['id'] = f"{filename.split('_')[0]}_{order_number}"
            
            # Save updated purchase record
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(purchase, f, ensure_ascii=False, indent=4)
            logger.info(f"Document {filename} has been successfully updated!")
            # time.sleep(1)

    def randomized_prompt_elements(self, sentiments, topics, products, agents, customers):
        return (
            random.choice(sentiments),
            random.choice(topics),
            random.choice(products),
            random.choice(agents),
            random.choice(customers)
        )

    def synthesize_human_conversations(self):
        # Load all purchases to link conversations to actual customer purchases
        purchases = []
        purchases_directory = os.path.join(self.base_dir, "Cosmos_Purchases")
        for filename in os.listdir(purchases_directory):
            file_path = os.path.join(purchases_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                purchase = json.load(f)
                purchases.append(purchase)
        
        logger.info(f"Loaded {len(purchases)} purchases for conversation generation")
        
        # Generate one conversation per purchase
        for idx, purchase in enumerate(purchases):
            customer_id = purchase.get('customer_id')
            product_id = purchase.get('product_id')
            order_number = purchase.get('order_number')
            product_details = purchase.get('product_details', {})
            product_name = product_details.get('name', 'product')
            delivered_date_str = purchase.get('delivered_date', '')

            # Get customer's first name
            customer_first_name = self.get_customer_name(customer_id)
            
            # Calculate conversation date: 1-7 days after delivery
            conversation_date = None
            if delivered_date_str:
                try:
                    # Parse delivery date - handle common formats
                    delivered_date = datetime.fromisoformat(delivered_date_str.replace('Z', '+00:00'))
                    # Add random 1-7 days
                    days_after_delivery = random.randint(1, 7)
                    conversation_datetime = delivered_date + timedelta(days=days_after_delivery)
                    conversation_date = conversation_datetime.isoformat()
                except Exception as e:
                    logger.warning(f"Could not parse delivery date '{delivered_date_str}': {e}")
                    conversation_date = None
            
            # Randomly select sentiment, topic, and agent
            random_sentiment = random.choice(SENTIMENTS_LIST)
            random_topic = random.choice(TOPICS_LIST)
            random_agent = random.choice(AGENT_LIST)
            
            # Create prompt for Azure OpenAI with purchase context
            document_creation_prompt = f"""CREATE a JSON document of a conversation between a customer and an agent.
            The customer {customer_first_name} (customer_id: {customer_id}) is calling about their order {order_number}.
            They purchased {product_name} (product_id: {product_id}).
            
            Sentiment: {random_sentiment}
            Topic: {random_topic}
            Agent: {random_agent}
            
            The required schema for the document is to follow the example below:
            {{
                "conversation_id": "string",
                "customer_id": "{customer_id}",
                "agent_id": "string",
                "messages": [
                    {{
                        "sender": "customer",
                        "message": "Hello, I need help with my {product_name}."
                    }},
                    {{
                        "sender": "agent",
                        "message": "Sure, I'd be happy to assist you with your {product_name}."
                    }}
                ],
                "sentiment": "{random_sentiment}",
                "topic": "{random_topic}"
            }}
            Be creative about the messages and do not use markdown to format the json object.
            The customer_id MUST be exactly: {customer_id}
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = self.create_document_name(idx, random_sentiment, random_topic, product_name)
            file_path = os.path.join(self.base_dir, "Cosmos_HumanConversations", document_name)
            
            # Save the generated document to the local folder
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            logger.info(f"Document {document_name} has been successfully created!")
        
        # Additional logic to update human conversations:
        # loop through the files in the local folder Cosmos_HumanConversations and update them
        directory = os.path.join(self.base_dir, "Cosmos_HumanConversations")
        
        # Rebuild purchase lookup for metadata enrichment
        purchase_by_index = {}
        for idx, purchase in enumerate(purchases):
            purchase_by_index[idx] = purchase
        
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                document = json.load(f)
                filename = file.split('.')[0]
                
                # Extract index from filename to match with purchase
                file_index = int(filename.split('_')[0])
                
                # add the "sentiment", "topic" and "product" key based on the file name to each JSON file
                sentiment, topic, product = filename.split('_')[1], filename.split('_')[2], '_'.join(filename.split('_')[3:])
                document["sentiment"] = sentiment
                document["topic"] = topic
                document["product"] = product
                
                # Add purchase-related metadata
                if file_index in purchase_by_index:
                    purchase = purchase_by_index[file_index]
                    document["order_number"] = purchase.get('order_number')
                    document["product_id"] = purchase.get('product_id')
                    # Ensure customer_id is from the purchase (real customer)
                    document["customer_id"] = purchase.get('customer_id')
                    
                    # Calculate conversation date: 1-7 days after delivery
                    delivered_date_str = purchase.get('delivered_date', '')
                    if delivered_date_str:
                        try:
                            delivered_date = datetime.fromisoformat(delivered_date_str.replace('Z', '+00:00'))
                            days_after_delivery = random.randint(1, 7)
                            conversation_datetime = delivered_date + timedelta(days=days_after_delivery)
                            document["conversation_date"] = conversation_datetime.isoformat()
                        except Exception as e:
                            logger.warning(f"Could not calculate conversation date for {file}: {e}")
                            document["conversation_date"] = None
                    else:
                        document["conversation_date"] = None
                
                # Generate session_id and id
                session_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{document['customer_id']}_{document['agent_id']}_{document['sentiment']}_{document['topic']}_{document['product']}").hex
                document['session_id'] = session_id
                document['id'] = f"chat_{filename.split('_')[0]}_{session_id}"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(document, f, ensure_ascii=False, indent=4)
            logger.info(f"Document {file} has been successfully updated!")


def run_synthesis(company_name, num_customers, num_products):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    # Ensure the assets directory structure exists
    base_assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    for dir_name in ['Cosmos_Customer', 'Cosmos_Product', 'Cosmos_Purchases', 'Cosmos_HumanConversations', 'Cosmos_ProductUrl']:
        os.makedirs(os.path.join(base_assets_dir, dir_name), exist_ok=True)
    # print(f"Base directory: {base_dir}")
    synthesizer = DataSynthesizer(base_dir)
    synthesizer.synthesize_everything(company_name, num_customers, num_products)
