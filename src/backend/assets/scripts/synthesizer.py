import os
import json
import uuid
import random
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
from datetime import datetime

# Constants for synthesis
SENTIMENTS_LIST = ['positive', 'negative', 'neutral', 'mixed', 'content', 'upset', 'angry', 'frustrated', 'happy', 'disappointed', 'confused']
TOPICS_LIST = ['churn', 'assistance', 'support', 'information', 'billing', 'payment', 'account', 'service', 'Quality', 'Sustainability']
AGENT_LIST = ['adam','betrace','curie','davinci','emil', 'fred']
FIRST_NAME_LIST = ['Alex','Brian','Chloe','David','Emma','Fiona','George','Hannah','Ian','Julia','Kevin','Lucy','Michael',
    'Nicole','Oliver','Paula','Quinn','Rachel','Samuel','Tara','Ursula','Victor','Wendy','Xander','Yvonne','Zachary']
LAST_NAME_LIST = ["Anderson", "Brown", "Clark", "Davis", "Evans", "Foster", "Garcia", "Harris", "Ingram", "Johnson", "King", 
                  "Lewis", "Martin", "Nelson", "Owens", "Parker", "Quinn", "Robinson", "Smith", "Taylor", "Underwood", 
                  "Vargas", "Wilson", "Xavier", "Young", "Zimmerman"]

class DataSynthesizer:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.setup_azure_clients()
        self.setup_cosmos_containers()

    def setup_azure_clients(self):
        self.aoai_client = AzureOpenAI(
            api_key=os.getenv("AOAI_API_KEY"),
            api_version=os.getenv("AOAI_API_VERSION"),
            azure_endpoint=os.getenv("AOAI_API_BASE")
        )
        
        self.cosmos_client = CosmosClient(
            os.getenv("COSMOS_ENDPOINT"), 
            DefaultAzureCredential()
        )
        self.database = self.cosmos_client.get_database_client(os.getenv("COSMOS_DATABASE"))

    def setup_cosmos_containers(self):
        self.containers = {
            'customer': self.database.get_container_client("Customer"),
            'product': self.database.get_container_client("Product"),
            'purchases': self.database.get_container_client("Purchases"),
            'human_conversations': self.database.get_container_client("Human_Conversations")
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
    def create_document(self, prompt, temperature=0.9, max_tokens=2000):
        response = self.aoai_client.chat.completions.create(
            model=os.getenv("AOAI_GPT4O_MINI_MODEL"),
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
                    print(f"Document {filename} has been successfully created in Azure Cosmos DB!")
                except Exception as e:
                    print(f"Error uploading {filename}: {str(e)}")
    # delete all json files in the assets folder recursively
    def delete_json_files(self, base_dir):
        assets_dir = os.path.join(base_dir, "..", "..", "assets")
        # Walk through the directory and delete JSON files
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")  # Optional: Print out deleted file paths for confirmation

    def synthesize_everything(self, company_name, num_customers, num_products, num_conversations):
        
        # Create required directories
        for dir_name in ['Cosmos_Customer', 'Cosmos_Product', 'Cosmos_Purchases', 'Cosmos_HumanConversations']:
            os.makedirs(os.path.join(self.base_dir, '../', dir_name), exist_ok=True)

        # Refresh Cosmos DB containers
    # create a container for Customer
        customer_container_name = "Customer"
        self.refresh_container(self.database, customer_container_name, "/customer_id")
        customer_container = self.database.get_container_client(customer_container_name)
        # create a container for Product
        product_container_name = "Product"
        self.refresh_container(self.database, product_container_name, "/product_id")
        product_container = self.database.get_container_client(product_container_name)
        # create a container for Purchases
        purchases_container_name = "Purchases"
        self.refresh_container(self.database, purchases_container_name, "/customer_id")
        purchases_container = self.database.get_container_client(purchases_container_name)
        # create a container for the human conversations
        human_conversations_container_name = "Human_Conversations"
        self.refresh_container(self.database, human_conversations_container_name, "/customer_id")
        human_conversations_container = self.database.get_container_client(human_conversations_container_name)
        # create a container for the AI conversations. 
        ai_conversations_container_name = "AI_Conversations"
        self.refresh_container(self.database, ai_conversations_container_name, "/customer_id")
        ai_conversations_container = self.database.get_container_client(ai_conversations_container_name)

        # Delete all JSON files in the assets folder
        self.delete_json_files(self.base_dir)
        # Generate all data types
        self.create_product_and_url_list(company_name, num_products)
        self.synthesize_customer_profiles(num_customers)
        self.synthesize_product_profiles(company_name)
        self.synthesize_purchases()
        self.synthesize_human_conversations(num_conversations, company_name)

        # Upload all data to Cosmos DB
        for folder, container in [
            ('Cosmos_Customer', self.containers['customer']),
            ('Cosmos_Product', self.containers['product']),
            ('Cosmos_Purchases', self.containers['purchases']),
            ('Cosmos_HumanConversations', self.containers['human_conversations'])
        ]:
            self.save_json_files_to_cosmos_db(os.path.join(self.base_dir, '../', folder), container)
        print("Data synthesis completed successfully!")

    def create_product_and_url_list(self, company_name, number_of_product):
        
        product_and_url_creation_prompt = f"""generate a json list of {number_of_product} most popular product at brand level of the company {company_name}, and the official website url of those products. 
                Example for microsoft: Xbox, Surface, Windows, Office, Azure. Example for apple: iPhone, iPad, Mac, Apple Watch, AirPods. Example for Unilever: Dove, Lipton, Hellmann's, Knorr, Ben & Jerry's.
                The list contains two keys: 'products' and 'urls'. The 'products' key contains the list of products and the 'urls' key contains the list of urls."""
        # Generate the document using Azure OpenAI
        generated_document = self.create_document(product_and_url_creation_prompt)
        # Create a dynamic document name
        document_name = f"{company_name}_products_and_urls.json"
        # Save the generated document to the local folder
        file_path = os.path.join(self.base_dir, "../Products_and_Urls_List", document_name)
        # save the generated_list as json file to local file folder Products_and_Urls_List. Make sure to write the file in utf-8 encoding
        with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
        print(f"Document {document_name} has been successfully created!")
        return json.loads(generated_document)

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
            file_path = os.path.join(self.base_dir, "../Cosmos_Customer", document_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            print(f"Document {document_name} has been successfully created!")
        
        # Update the JSON files with customer_id and id fields
        directory = os.path.join(self.base_dir, "../Cosmos_Customer")
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                customer_profile = json.load(f)
                customer_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{customer_profile['first_name']}_{customer_profile['last_name']}").hex
                customer_profile['customer_id'] = customer_id
                customer_profile['id'] = f"{filename.split('_')[0]}_{customer_id}"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(customer_profile, f, ensure_ascii=False, indent=4)
            print(f"Document {filename} has been successfully updated!")

    def synthesize_product_profiles(self, company_name):
        producturls_file_path = os.path.join(self.base_dir, "../Products_and_Urls_List", f"{company_name}_products_and_urls.json")
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
                "unit_price": "number",
                "weight": {{
                    "value": "number",
                    "unit": "string"
                }},
                "color": "string", 
                "material": "string"
            }}
            Be creative about the values and do not use markdown to format the json object. if any field is not applicable, leave it empty.
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = f"{idx}_{product.replace(' ', '_')}.json"
            file_path = os.path.join(self.base_dir, "../Cosmos_Product", document_name)
            
            # Save the generated document to the local folder
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            print(f"Document {document_name} has been successfully created!")
        
        # Additional logic to update product profiles:
        # loop through the files in the local folder Cosmos_Product and update them:
        # 1. add a product_id field (hash value based on the current file name) to the content
        # 2. add a id field (hash value based on the prefix value of the current file name and the product_id) to the content
        # 3. save the updated content back to the file
        directory = os.path.join(self.base_dir, "../Cosmos_Product")
        for filename in os.listdir(directory):
            path = os.path.join(directory, filename)
            with open(path, 'r', encoding='utf-8') as f:
                product_profile = json.load(f)
                product_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{filename}").hex
                product_profile['product_id'] = product_id
                product_profile['id'] = f"{filename.split('_')[0]}_{product_id}"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(product_profile, f, ensure_ascii=False, indent=4)
            print(f"Document {filename} has been successfully updated!")

    # def create_document_name(self, index, product_id, customer_id, suffix):
    #     return f"{index}_{product_id}_{customer_id}{suffix}.json"

    def get_today_date(self):
        return datetime.today().strftime("%B %d, %Y")

    def get_product_profile(self, product_id):
        query = f"""
        SELECT 
            c.name, 
            c.category, 
            c.type, 
            c.brand, 
            c.unit_price, 
            c.weight, 
            c.color, 
            c.material 
        FROM c WHERE c.product_id = '{product_id}'
        """
        items = list(self.containers['product'].query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {}

    def synthesize_purchases(self):
        # Loop through the files in Cosmos_Customer and Cosmos_Product to gather customer_ids and product_ids
        customer_ids = []
        product_ids = []
        customer_directory = os.path.join(self.base_dir, "../Cosmos_Customer")
        for filename in os.listdir(customer_directory):
            file_path = os.path.join(customer_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                customer_profile = json.load(f)
                customer_ids.append(customer_profile.get('customer_id'))
        
        product_directory = os.path.join(self.base_dir, "../Cosmos_Product")
        for filename in os.listdir(product_directory):
            file_path = os.path.join(product_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                product_profile = json.load(f)
                product_ids.append(product_profile.get('product_id'))
        
        # For each customer, generate 2 random purchase records with random product_id
        for idx, customer_id in enumerate(customer_ids):
            for i in range(2):
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
                document_name = self.create_document_name(idx*2+i+1, random_product_id, customer_id, "")

                # Save the JSON document to the local folder Cosmos_Purchases
                file_path = os.path.join(self.base_dir, "../Cosmos_Purchases", document_name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(generated_document)
                print(f"Document {document_name} has been successfully created!")
                # time.sleep(1)
        
        # Update the purchase records with additional fields
        purchases_directory = os.path.join(self.base_dir, "../Cosmos_Purchases")
        for filename in os.listdir(purchases_directory):
            file_path = os.path.join(purchases_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                purchase = json.load(f)
                order_number = uuid.uuid3(uuid.NAMESPACE_DNS, f"{filename}").hex
                purchase['order_number'] = order_number
                purchase['product_details'] = self.get_product_profile(purchase.get('product_id', ''))
                purchase['total_price'] = purchase['product_details'].get('unit_price', 0) * purchase.get('quantity', 0)
                purchase['id'] = f"{filename.split('_')[0]}_{order_number}"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(purchase, f, ensure_ascii=False, indent=4)
            print(f"Document {filename} has been successfully updated!")
            # time.sleep(1)

    def randomized_prompt_elements(self, sentiments, topics, products, agents, customers):
        return (
            random.choice(sentiments),
            random.choice(topics),
            random.choice(products),
            random.choice(agents),
            random.choice(customers)
        )

    def synthesize_human_conversations(self, num_conversations, company_name):
        # product list is defined by the only json file in the local folder Products_and_Urls_List, in the "product" key
        producturls_file_path = os.path.join(self.base_dir, "../Products_and_Urls_List", f"{company_name}_products_and_urls.json")
        with open(producturls_file_path, "r", encoding="utf-8") as f:
            PRODUCTS_LIST = json.load(f)["products"]
        for i in range(num_conversations):
            # Randomly select elements for the conversation
            random_sentiment, random_topic, random_product, random_agent, random_customer = self.randomized_prompt_elements(
                SENTIMENTS_LIST, TOPICS_LIST, PRODUCTS_LIST, AGENT_LIST, FIRST_NAME_LIST
            )
            
            # Create prompt for Azure OpenAI
            document_creation_prompt = f"""CREATE a JSON document of a conversation between a customer and an agent.
            Sentiment: {random_sentiment}
            Topic: {random_topic}
            Product: {random_product}
            Agent: {random_agent}
            Customer: {random_customer}
            The required schema for the document is to follow the example below:
            {{
                "conversation_id": "string",
                "customer_id": "string",
                "agent_id": "string",
                "messages": [
                    {{
                        "sender": "customer",
                        "message": "Hello, I need help with my {random_product}."
                    }},
                    {{
                        "sender": "agent",
                        "message": "Sure, I'd be happy to assist you with your {random_product}."
                    }}
                ],
                "sentiment": "{random_sentiment}",
                "topic": "{random_topic}"
            }}
            Be creative about the messages and do not use markdown to format the json object.
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = self.create_document_name(i, random_sentiment, random_topic, random_product)
            file_path = os.path.join(self.base_dir, "../Cosmos_HumanConversations", document_name)
            
            # Save the generated document to the local folder
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            print(f"Document {document_name} has been successfully created!")
        
        # Additional logic to update human conversations:
        # loop through the files in the local folder Cosmos_HumanConversations and update them:
        # 1. read the file and load the content
        # 2. create a hash value of the combination of customer_id and agent_id and assign it to the conversation_id
        # 3. add a id field with the value of the current iteration index number plus the conversation_id
        # 4. save the updated content back to the file
        directory = os.path.join(self.base_dir, "../Cosmos_HumanConversations")
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                document = json.load(f)
                filename = file.split('.')[0]
                # add the "sentiment", "topic" and "product" key based on the file name to each JSON file
                sentiment, topic, product = filename.split('_')[1], filename.split('_')[2], filename.split('_')[3]
                document["sentiment"] = sentiment
                document["topic"] = topic
                document["product"] = product
                session_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{document['customer_id']}_{document['agent_id']}_{document['sentiment']}_{document['topic']}_{document['product']}").hex
                document['session_id'] = session_id
                document['id'] = f"chat_{filename.split('_')[0]}_{session_id}"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(document, f, ensure_ascii=False, indent=4)
            print(f"Document {file} has been successfully updated!")


def run_synthesis(company_name, num_customers, num_products, num_conversations):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    synthesizer = DataSynthesizer(base_dir)
    synthesizer.synthesize_everything(company_name, num_customers, num_products, num_conversations)
