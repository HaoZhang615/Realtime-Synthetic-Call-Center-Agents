import json
import os
import uuid
import random
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from datetime import datetime
from utils import load_dotenv_from_azd


load_dotenv_from_azd()
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

# Constants for Swiss roadside assistance synthesis
SENTIMENTS_LIST = ['positive', 'negative', 'neutral', 'mixed', 'content', 'upset', 'angry', 'frustrated', 'happy', 'disappointed', 'confused', 'stressed', 'relieved', 'worried', 'panicked']

TOPICS_LIST = ['pannenhilfe', 'abschleppdienst', 'starthilfe', 'reifenpanne', 'schlüsseldienst', 'kraftstoffservice', 'unfall_hilfe', 'versicherung_frage', 'rechnung_frage', 'termin_vereinbarung']

BREAKDOWN_CAUSES = ['motorschaden', 'batterie_leer', 'reifenpanne', 'kraftstoff_leer', 'ausgesperrt', 'überhitzung', 'elektrisches_problem', 'getriebeschaden', 'anlasser_defekt', 'lichtmaschine_defekt', 'bremsen_problem', 'unfallschaden']

VEHICLE_MAKES = ['BMW', 'Mercedes-Benz', 'Audi', 'Volkswagen', 'Opel', 'Ford', 'Toyota', 'Honda', 'Peugeot', 'Renault', 'Fiat', 'Skoda', 'Seat', 'Hyundai', 'Kia', 'Nissan', 'Volvo', 'Subaru']

INSURANCE_TYPES = ['privat', 'unternehmen', 'flotte']

URGENCY_LEVELS = ['sofort', 'binnen_stunde', 'heute', 'nicht_dringend']

AGENT_LIST = ['adam','beatrice','christian','diana','emil', 'franziska']

# Swiss German first names
FIRST_NAME_LIST = ['Andreas','Beatrice','Christian','Diana','Emil','Franziska','Georg','Hannah','Isabelle','Jakob','Klaus','Lieselotte','Marcel',
    'Nicole','Oliver','Petra','Quentin','Rebecca','Stefan','Tanja','Ulrich','Verena','Wilhelm','Xaver','Yvonne','Zacharias']

# Swiss surnames
LAST_NAME_LIST = ["Müller", "Meier", "Schmid", "Keller", "Weber", "Huber", "Schneider", "Meyer", "Steiner", "Fischer", "Gerber", 
                  "Brunner", "Baumann", "Frei", "Zimmermann", "Moser", "Lüthi", "Graf", "Wyss", "Roth", "Kaufmann", 
                  "Zürcher", "Hofmann", "Widmer", "Bürki", "Lehmann"]

# Swiss cantons for license plates
SWISS_CANTONS = ['ZH', 'BE', 'LU', 'UR', 'SZ', 'OW', 'NW', 'GL', 'ZG', 'FR', 'SO', 'BS', 'BL', 'SH', 'AR', 'AI', 'SG', 'GR', 'AG', 'TG', 'TI', 'VD', 'VS', 'NE', 'GE', 'JU']

# Environment variables - Updated for roadside assistance
cosmos_customer_container_name = os.environ["COSMOSDB_Customer_CONTAINER"]
cosmos_vehicles_container_name = os.environ.get("COSMOSDB_Vehicles_CONTAINER", "Vehicles")
cosmos_assistance_cases_container_name = os.environ.get("COSMOSDB_AssistanceCases_CONTAINER", "AssistanceCases")
cosmos_ai_conversations_container_name = os.environ["COSMOSDB_AIConversations_CONTAINER"]
cosmos_human_conversations_container_name = os.environ["COSMOSDB_HumanConversations_CONTAINER"]
cosmos_service_types_container_name = os.environ.get("COSMOSDB_ServiceTypes_CONTAINER", "ServiceTypes")

class DataSynthesizer:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.used_license_plates = set()  # Track used license plates to ensure uniqueness
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
            'customer': self.database.get_container_client(cosmos_customer_container_name),
            'vehicles': self.database.get_container_client(cosmos_vehicles_container_name),
            'assistance_cases': self.database.get_container_client(cosmos_assistance_cases_container_name),
            'human_conversations': self.database.get_container_client(cosmos_human_conversations_container_name),
            'service_types': self.database.get_container_client(cosmos_service_types_container_name),
        }

    def generate_unique_license_plate(self):
        """Generate a unique Swiss license plate in format: [Canton][Number] for each customer (not each vehicle)"""
        max_attempts = 1000  # Prevent infinite loops
        attempts = 0
        
        while attempts < max_attempts:
            canton = random.choice(SWISS_CANTONS)
            # Swiss license plates typically have 6 digits after the canton code
            number = random.randint(100000, 999999)
            license_plate = f"{canton}{number}"
            
            if license_plate not in self.used_license_plates:
                self.used_license_plates.add(license_plate)
                return license_plate
            
            attempts += 1
        
        # Fallback: if somehow we can't generate a unique plate, use timestamp
        import time
        timestamp_suffix = str(int(time.time()))[-6:]
        canton = random.choice(SWISS_CANTONS)
        license_plate = f"{canton}{timestamp_suffix}"
        self.used_license_plates.add(license_plate)
        return license_plate

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
            model=os.environ["AZURE_OPENAI_GPT41_NANO_DEPLOYMENT"],
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

            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Skipping {filename}: failed to load JSON ({e})")
                continue

            partition_key_path = container.read()['partitionKey']['paths'][0].strip('/')
            partition_key_value = data.get(partition_key_path)

            if not partition_key_value:
                print(f"❌ ERROR: {filename} missing partition key '{partition_key_path}' in document")
                print(f"   Available keys: {list(data.keys())}")
                print(f"   Document preview: {str(data)[:200]}...")
                continue

            try:
                container.upsert_item(body=data)
                print(f"✅ Uploaded {filename} -> pk={partition_key_value}")
            except Exception as e:
                print(f"❌ Error uploading {filename}: {e}")
    
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

    def synthesize_everything(self, company_name, num_customers, num_service_types, num_conversations):
        # Reset license plate tracker for new synthesis
        self.used_license_plates.clear()
        
        # Refresh Cosmos DB containers for roadside assistance
        self.refresh_container(self.database, cosmos_service_types_container_name, "/company_name")
        self.refresh_container(self.database, cosmos_customer_container_name, "/customer_id")
        self.refresh_container(self.database, cosmos_vehicles_container_name, "/license_plate")  # Most granular level
        self.refresh_container(self.database, cosmos_assistance_cases_container_name, "/case_id")
        self.refresh_container(self.database, cosmos_human_conversations_container_name, "/customer_id")
        self.refresh_container(self.database, cosmos_ai_conversations_container_name, "/customer_id")
        
        # Delete all JSON files in the assets folder
        self.delete_json_files(self.base_dir)
        
        # Generate roadside assistance data
        self.create_service_types_list(company_name, num_service_types)
        self.synthesize_customer_profiles(num_customers)
        self.synthesize_vehicle_profiles(num_customers)  # Will create multiple vehicles per customer
        self.synthesize_assistance_cases()
        self.synthesize_human_conversations(num_conversations, company_name)

        # Upload all data to Cosmos DB
        for folder, container in [
            ('Cosmos_ServiceTypes', self.containers['service_types']),
            ('Cosmos_Customer', self.containers['customer']),
            ('Cosmos_Vehicles', self.containers['vehicles']),
            ('Cosmos_AssistanceCases', self.containers['assistance_cases']),
            ('Cosmos_HumanConversations', self.containers['human_conversations'])
        ]:
            self.save_json_files_to_cosmos_db(os.path.join(self.base_dir, folder), container)
        
        # Validate license plate distribution (2 cars per customer with same plate)
        self.validate_unique_license_plates()
        
        print("Swiss roadside assistance data synthesis completed successfully!")

    def create_service_types_list(self, company_name, number_of_services):
        service_creation_prompt = f"""generate a json list of {number_of_services} roadside assistance services offered by Swiss insurance company {company_name}.
        Examples: Pannenhilfe vor Ort, Abschleppdienst, Starthilfe, Reifenpanne, Schlüsseldienst, Kraftstoffservice, Unfallhilfe.
        The list contains two keys: 'services' and 'descriptions'.
        Services should be in German (Swiss context).
        """
        generated_document = self.create_document(service_creation_prompt)
        data = json.loads(generated_document)
        enhanced_document = {
            'company_name': company_name,
            'id': f"{company_name}_service_types",
            'services': data['services'],
            'descriptions': data['descriptions']
        }
        
        document_name = f"{company_name}_service_types.json"
        file_path = os.path.join(self.base_dir, "Cosmos_ServiceTypes", document_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_document, f, ensure_ascii=False, indent=4)    
        print(f"Document {document_name} has been successfully created!")

    def synthesize_customer_profiles(self, num_customers):
        for i in range(num_customers):
            # Randomly select first and last names
            random_firstname = random.choice(FIRST_NAME_LIST)
            random_lastname = random.choice(LAST_NAME_LIST)
            
            # Create prompt for Azure OpenAI
            document_creation_prompt = f"""CREATE a JSON document of a Swiss customer profile for roadside assistance service whose first name is {random_firstname} and last name is {random_lastname}. 
            This follows the Swiss/German roadside assistance procedure Level 1 - Identifikation & Deckungsprüfung:
            {{
                "first_name": "Andreas",
                "last_name": "Müller",
                "date_of_birth": "1985-03-15",
                "gender": "male",
                "email": "andreas.mueller@example.ch",
                "address": {{
                    "street": "Bahnhofstrasse 42",
                    "city": "Zürich",
                    "postal_code": "8001",
                    "canton": "ZH",
                    "country": "Schweiz"
                }},
                "phone_number": "+41791234567",
                "insurance_type": "privat",
                "customer_since": "2020-01-15",
                "membership_number": "MOB123456789",
                "language_preference": "deutsch"
            }}
            Use realistic Swiss addresses, postal codes, phone numbers (+41 format), and .ch email addresses. 
            Swiss cities examples: Zürich, Basel, Bern, Lausanne, Genf, Winterthur, Luzern, St. Gallen, Lugano, Biel.
            Swiss cantons: ZH, BE, LU, UR, SZ, OW, NW, GL, ZG, FR, SO, BS, BL, SH, AR, AI, SG, GR, AG, TG, TI, VD, VS, NE, GE, JU.
            The insurance_type should be one of: privat, unternehmen, flotte.
            Do not use markdown to format the json object.
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = f"{i}_{random_firstname}_{random_lastname}.json"
            
            # Save the generated document to the local folder
            file_path = os.path.join(self.base_dir, "Cosmos_Customer", document_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(generated_document)
            print(f"Document {document_name} has been successfully created!")
        
        # Update the JSON files with customer_id and id fields
        directory = os.path.join(self.base_dir, "Cosmos_Customer")
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                customer_profile = json.load(f)
                customer_id = str(int(filename.split('_')[0]) + 1)
                customer_profile['customer_id'] = customer_id
                customer_profile['id'] = f"{customer_id}_{uuid.uuid3(uuid.NAMESPACE_DNS, f"{customer_profile['first_name']}_{customer_profile['last_name']}_{customer_profile['date_of_birth']}").hex}"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(customer_profile, f, ensure_ascii=False, indent=4)
            print(f"Document {filename} has been successfully updated!")

    def synthesize_vehicle_profiles(self, num_customers):
        """
        Generate vehicle profiles with new logic:
        - Each customer has exactly 2 vehicles
        - Both vehicles share the same license plate number
        - Both vehicles share the same policy number  
        - Create SINGLE JSON file per customer with both vehicles in clean array
        """
        # Get customer IDs to link vehicles
        customer_ids = self.get_customer_ids()
        
        vehicle_count = 0
        for customer_id in customer_ids:
            # Each customer has exactly 2 vehicles with the same license plate
            num_vehicles_per_customer = 2
            shared_license_plate = self.generate_unique_license_plate()  # Generate one license plate for both cars
            shared_policy_number = random.randint(10000, 99999)  # Same policy number for both cars
            
            vehicles_array = []  # Store both vehicles in this array
            primary_make = None  # Use first vehicle's make for file naming
            
            for i in range(num_vehicles_per_customer):
                random_make = random.choice(VEHICLE_MAKES)
                if i == 0:
                    primary_make = random_make  # Use first vehicle's make for filename
                
                # Create a simple vehicle object directly (no AI generation to avoid nesting issues)
                vehicle_models = {
                    "BMW": ["3er", "5er", "X3", "X5"],
                    "Mercedes": ["C-Klasse", "E-Klasse", "GLC", "GLA"],
                    "Audi": ["A3", "A4", "Q3", "Q5"],
                    "Volkswagen": ["Golf", "Passat", "Tiguan", "Polo"],
                    "Toyota": ["Corolla", "Camry", "RAV4", "Prius"],
                    "Hyundai": ["Elantra", "Tucson", "Kona", "i30"],
                    "Skoda": ["Octavia", "Fabia", "Kodiaq", "Superb"],
                    "Seat": ["Ibiza", "Leon", "Ateca", "Tarraco"]
                }
                
                # Generate realistic VIN
                vin_prefixes = {
                    "BMW": "WBABA91060AL",
                    "Mercedes": "WDB1840312A",
                    "Audi": "WAUZZZ8K2DA", 
                    "Volkswagen": "WVWZZZ1EZKW",
                    "Toyota": "JTDBE32K123",
                    "Hyundai": "KMHD84LF4JU",
                    "Skoda": "TMBJF7NE8J0",
                    "Seat": "VSSZZZ1MZ9R"
                }
                
                model = random.choice(vehicle_models.get(random_make, ["Standard"]))
                year = random.randint(2018, 2023)
                colors = ["Schwarz", "Weiss", "Blau", "Rot", "Grau", "Silber"]
                color = random.choice(colors)
                
                vehicle_data = {
                    "make": random_make,
                    "model": model,
                    "year": year,
                    "vin": f"{vin_prefixes.get(random_make, 'UNKNOWN12345')}{random.randint(100000, 999999)}",
                    "color": color,
                    "policy_number": shared_policy_number,
                    "engine": {
                        "type": "Benzin",
                        "displacement": f"{random.uniform(1.0, 3.0):.1f}L",
                        "horsepower": random.randint(90, 300)
                    },
                    "mileage": random.randint(5000, 150000),
                    "first_registration": f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    "next_inspection": f"{year+3}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    "fuel_type": "Benzin"
                }
                
                # Add vehicle to array
                vehicles_array.append(vehicle_data)
            
            # Create the combined document with clean structure and required Cosmos DB fields
            combined_document = {
                "vehicles": vehicles_array,
                "license_plate": shared_license_plate,  # Partition key
                "customer_id": customer_id,
                "policy_number": shared_policy_number,
                "id": f"{vehicle_count + 1}_{uuid.uuid3(uuid.NAMESPACE_DNS, f'{shared_license_plate}_{customer_id}').hex}"  # Required for Cosmos DB
            }
            
            # Generate single document name and save
            document_name = f"{vehicle_count}_{primary_make}_customer_{customer_id[:8]}_vehicles.json"
            file_path = os.path.join(self.base_dir, "Cosmos_Vehicles", document_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(combined_document, f, ensure_ascii=False, indent=4)
            print(f"Document {document_name} has been successfully created with {len(vehicles_array)} vehicles sharing license plate {shared_license_plate}!")
            vehicle_count += 1

    def synthesize_assistance_cases(self):
        # Get customer and vehicle IDs with their relationships
        customer_vehicle_pairs = self.get_customer_vehicle_pairs()
        
        case_count = 0
        for customer_id, vehicle_license_plate in customer_vehicle_pairs:
            # Generate 0-1 assistance cases per vehicle (not all vehicles will have cases)
            if random.random() < 0.3:  # 30% chance of having a case
                random_breakdown_cause = random.choice(BREAKDOWN_CAUSES)
                random_urgency = random.choice(URGENCY_LEVELS)
                
                document_creation_prompt = f"""CREATE a JSON document of a Swiss roadside assistance case.
                This follows the German/Swiss procedure levels 3-7 (Pannenursache, Pannenort, Beteiligte, Dringlichkeit, Sonstiges).
                The case is for customer_id: {customer_id} and vehicle with license plate: {vehicle_license_plate}
                {{
                    "customer_id": "{customer_id}",
                    "license_plate": "{vehicle_license_plate}",
                    "case_date": "2024-12-01T14:30:00Z",
                    "breakdown_cause": "batterie_leer",
                    "breakdown_location": {{
                        "is_at_home": false,
                        "address": "Autobahn A1, Raststätte Grauholz",
                        "city": "Bern",
                        "postal_code": "3063",
                        "canton": "BE",
                        "coordinates": {{
                            "latitude": 46.9481,
                            "longitude": 7.4474
                        }}
                    }},
                    "involved_parties": {{
                        "adults": 2,
                        "children": 1
                    }},
                    "urgency_level": "sofort",
                    "additional_notes": "Fahrzeug steht auf dem Pannenstreifen, Warnblinker eingeschaltet",
                    "status": "offen",
                    "estimated_arrival_time": "2024-12-01T15:15:00Z",
                    "service_provider": "TCS Pannenhilfe",
                    "cost_estimate": 150.00,
                    "case_language": "deutsch"
                }}
                The breakdown_cause should be: {random_breakdown_cause}
                The urgency_level should be: {random_urgency}
                Today is {self.get_today_date()}, case_date should be within the last 30 days.
                Use realistic Swiss locations (cities, postal codes, cantons, highways like A1, A2, A3, A4, A6, A7, A8, A9).
                Status should be in German: offen, in_bearbeitung, abgeschlossen, storniert.
                Do not use markdown to format the json object.
                """
                
                generated_document = self.create_document(document_creation_prompt)
                document_name = f"{case_count}_{random_breakdown_cause}_{vehicle_license_plate.replace(' ', '_')}_case.json"
                
                file_path = os.path.join(self.base_dir, "Cosmos_AssistanceCases", document_name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(generated_document)
                print(f"Document {document_name} has been successfully created!")
                case_count += 1
        
        # Update with case_id and id fields
        directory = os.path.join(self.base_dir, "Cosmos_AssistanceCases")
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                case = json.load(f)
                case_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{filename}_{case['case_date']}").hex
                case['case_id'] = case_id
                case['id'] = f"{filename.split('_')[0]}_{case_id}"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(case, f, ensure_ascii=False, indent=4)
            print(f"Document {filename} has been successfully updated!")

    def get_customer_ids(self):
        customer_ids = []
        customer_directory = os.path.join(self.base_dir, "Cosmos_Customer")
        if os.path.exists(customer_directory):
            for filename in os.listdir(customer_directory):
                file_path = os.path.join(customer_directory, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    customer_profile = json.load(f)
                    customer_ids.append(customer_profile.get('customer_id'))
        return customer_ids

    def get_customer_vehicle_pairs(self):
        """Returns pairs of (customer_id, license_plate) for assistance case generation"""
        pairs = []
        vehicle_directory = os.path.join(self.base_dir, "Cosmos_Vehicles")
        if os.path.exists(vehicle_directory):
            for filename in os.listdir(vehicle_directory):
                file_path = os.path.join(vehicle_directory, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    vehicle_profile = json.load(f)
                    customer_id = vehicle_profile.get('customer_id')
                    license_plate = vehicle_profile.get('license_plate')
                    if customer_id and license_plate:
                        pairs.append((customer_id, license_plate))
        return pairs

    def get_today_date(self):
        return datetime.today().strftime("%B %d, %Y")

    def validate_unique_license_plates(self):
        """Validate license plate distribution - each customer should have exactly 2 vehicles with the same plate"""
        vehicle_directory = os.path.join(self.base_dir, "Cosmos_Vehicles")
        
        if not os.path.exists(vehicle_directory):
            print("No vehicles directory found for validation")
            return
        
        customer_plates = {}  # customer_id -> license_plate
        plate_counts = {}     # license_plate -> count
        total_files = 0
        successful_reads = 0
        total_vehicles = 0
        
        for filename in os.listdir(vehicle_directory):
            if not filename.endswith('.json'):
                continue
            total_files += 1
            file_path = os.path.join(vehicle_directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    vehicle_data = json.load(f)
                    customer_id = vehicle_data.get('customer_id')
                    license_plate = vehicle_data.get('license_plate')
                    vehicles_array = vehicle_data.get('vehicles', [])
                    
                    if customer_id and license_plate and vehicles_array:
                        successful_reads += 1
                        vehicle_count = len(vehicles_array)
                        total_vehicles += vehicle_count
                        
                        # Track plates per customer (count vehicles, not files)
                        if customer_id not in customer_plates:
                            customer_plates[customer_id] = []
                        
                        # Add license plate for each vehicle in the array
                        for _ in range(vehicle_count):
                            customer_plates[customer_id].append(license_plate)
                        
                        # Count total occurrences of each plate
                        plate_counts[license_plate] = plate_counts.get(license_plate, 0) + vehicle_count
                    else:
                        print(f"WARNING: {filename} missing required fields: customer_id={customer_id}, license_plate={license_plate}, vehicles_count={len(vehicles_array) if vehicles_array else 0}")
                        
            except Exception as e:
                print(f"Error reading vehicle file {filename}: {e}")
        
        # Validate the structure
        total_customers = len(customer_plates)
        
        print(f"License plate validation:")
        print(f"- Read {successful_reads}/{total_files} vehicle files successfully")
        print(f"- {total_customers} customers with {total_vehicles} total vehicles")
        
        if total_vehicles == 0:
            print("❌ No vehicles found with valid customer_id and license_plate!")
            return
        
        # Check each customer has exactly 2 vehicles with same plate
        valid_customers = 0
        for customer_id, plates in customer_plates.items():
            if len(plates) == 2 and plates[0] == plates[1]:
                valid_customers += 1
            else:
                print(f"WARNING: Customer {customer_id} has {len(plates)} vehicles with plates: {plates}")
        
        # Check each plate appears exactly twice
        valid_plates = 0
        for plate, count in plate_counts.items():
            if count == 2:
                valid_plates += 1
            else:
                print(f"WARNING: License plate {plate} appears {count} times (should be 2)")
        
        if valid_customers == total_customers and valid_plates == len(plate_counts):
            print("✅ All customers have exactly 2 vehicles with matching license plates!")
        else:
            print(f"❌ Structure issues found: {valid_customers}/{total_customers} valid customers, {valid_plates}/{len(plate_counts)} valid plates")


    def randomized_prompt_elements(self, sentiments, topics, products, agents, customers):
        return (
            random.choice(sentiments),
            random.choice(topics),
            random.choice(products),
            random.choice(agents),
            random.choice(customers)
        )

    def synthesize_human_conversations(self, num_conversations, company_name):
        # service list is defined by the only json file in the local folder Cosmos_ServiceTypes, in the "services" key
        service_types_file_path = os.path.join(self.base_dir, "Cosmos_ServiceTypes", f"{company_name}_service_types.json")
        with open(service_types_file_path, "r", encoding="utf-8") as f:
            SERVICES_LIST = json.load(f)["services"]
        for i in range(num_conversations):
            # Randomly select elements for the conversation
            random_sentiment, random_topic, random_service, random_agent, random_customer = self.randomized_prompt_elements(
                SENTIMENTS_LIST, TOPICS_LIST, SERVICES_LIST, AGENT_LIST, FIRST_NAME_LIST
            )
            
            # Create prompt for Azure OpenAI
            document_creation_prompt = f"""CREATE a JSON document of a conversation between a Swiss customer and a roadside assistance agent.
            Sentiment: {random_sentiment}
            Topic: {random_topic}
            Service: {random_service}
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
                        "message": "Hallo, ich brauche Hilfe mit meinem Auto. Ich habe eine Panne."
                    }},
                    {{
                        "sender": "agent",
                        "message": "Guten Tag, gerne helfe ich Ihnen bei Ihrer Panne. Können Sie mir Ihren Namen und Ihr Kennzeichen nennen?"
                    }}
                ],
                "sentiment": "{random_sentiment}",
                "topic": "{random_topic}",
                "service": "{random_service}",
                "language": "deutsch"
            }}
            The conversation should follow the Swiss/German roadside assistance procedure levels (Identifikation, Fahrzeugidentifikation, Pannenursache, etc.).
            Use German language for the conversation messages as this is for Swiss customers.
            Be creative about the messages and do not use markdown to format the json object.
            """
            
            # Generate the document using Azure OpenAI
            generated_document = self.create_document(document_creation_prompt)
            
            # Create a dynamic document name
            document_name = self.create_document_name(i, random_sentiment, random_topic, random_service)
            file_path = os.path.join(self.base_dir, "Cosmos_HumanConversations", document_name)
            
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
        directory = os.path.join(self.base_dir, "Cosmos_HumanConversations")
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                document = json.load(f)
                filename = file.split('.')[0]
                # add the "sentiment", "topic" and "service" key based on the file name to each JSON file
                sentiment, topic, service = filename.split('_')[1], filename.split('_')[2], filename.split('_')[3]
                document["sentiment"] = sentiment
                document["topic"] = topic
                document["service"] = service
                session_id = uuid.uuid3(uuid.NAMESPACE_DNS, f"{document['customer_id']}_{document['agent_id']}_{document['sentiment']}_{document['topic']}_{document['service']}").hex
                document['session_id'] = session_id
                document['id'] = f"chat_{filename.split('_')[0]}_{session_id}"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(document, f, ensure_ascii=False, indent=4)
            print(f"Document {file} has been successfully updated!")


def run_synthesis(company_name, num_customers, num_service_types, num_conversations):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    # Ensure the assets directory structure exists for Swiss roadside assistance (removed Cosmos_Policy)
    base_assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    for dir_name in ['Cosmos_Customer', 'Cosmos_Vehicles', 'Cosmos_AssistanceCases', 'Cosmos_HumanConversations', 'Cosmos_ServiceTypes']:
        os.makedirs(os.path.join(base_assets_dir, dir_name), exist_ok=True)
    # print(f"Base directory: {base_dir}")
    synthesizer = DataSynthesizer(base_dir)
    synthesizer.synthesize_everything(company_name, num_customers, num_service_types, num_conversations)
