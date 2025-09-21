import logging
import os
import re
from subprocess import run, PIPE
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from rich.logging import RichHandler
from utils import load_dotenv_from_azd
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    AzureOpenAIEmbeddingSkill,
    AzureOpenAIVectorizerParameters,
    AzureOpenAIVectorizer,
    AIServicesAccountKey,
    AIServicesAccountIdentity,
    DocumentIntelligenceLayoutSkill,
    FieldMapping,
    HnswAlgorithmConfiguration,
    HnswParameters,
    IndexProjectionMode,
    InputFieldMappingEntry,
    IndexingParameters,
    IndexingParametersConfiguration,
    OutputFieldMappingEntry,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataSourceType,
    SearchIndexerDataUserAssignedIdentity,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    SearchIndexerSkillset,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    SplitSkill,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

# Load environment variables
load_dotenv_from_azd()

def get_keyvault_secret(credential, secret_uri):
    """Resolve a Key Vault secret reference to its actual value."""
    # Extract the vault URL and secret name from the Key Vault reference
    match = re.match(r'@Microsoft\.KeyVault\(SecretUri=https://([^\.]+)\.vault\.azure\.net/secrets/([^/]+)/\)', secret_uri)
    if match:
        vault_name = match.group(1)
        secret_name = match.group(2)
        vault_url = f"https://{vault_name}.vault.azure.net"
        
        # Create a SecretClient using the credential
        secret_client = SecretClient(vault_url=vault_url, credential=credential)
        
        # Retrieve the secret
        secret = secret_client.get_secret(secret_name)
        return secret.value
    
    # If it's not a Key Vault reference, return as is
    return secret_uri

def setup_index(
        azure_credential, 
        uami_id, 
        index_name, 
        azure_search_endpoint, 
        azure_storage_connection_string, 
        azure_storage_container, 
        azure_openai_embedding_endpoint, 
        azure_openai_embedding_deployment, 
        azure_openai_embedding_model, 
        azure_openai_embeddings_dimensions
        ):
    index_client = SearchIndexClient(azure_search_endpoint, azure_credential)
    indexer_client = SearchIndexerClient(azure_search_endpoint, azure_credential)
    logging.info(f"Using identity: {azure_credential.__class__.__name__}")
    logging.info(f"User assigned identity ID: {uami_id}")
    
    # Step 1: Create a data source connection to the blob storage container if it doesn't exist
    data_source_connections = indexer_client.get_data_source_connections()
    if index_name in [ds.name for ds in data_source_connections]:
        logging.info(f"Data source connection {index_name} already exists, not re-creating")
    else:
        logging.info(f"Creating data source connection: {index_name}")
        data_source_connection_name = f"{index_name}-data-source-connection"
        data_source_connection=SearchIndexerDataSourceConnection(
                name=data_source_connection_name, 
                type=SearchIndexerDataSourceType.AZURE_BLOB,
                connection_string=azure_storage_connection_string,
                identity = SearchIndexerDataUserAssignedIdentity(resource_id=uami_id),
                container=SearchIndexerDataContainer(name=azure_storage_container))
        data_source = indexer_client.create_or_update_data_source_connection(data_source_connection)
    # Step 2: Create the index if it doesn't exist
    index_names = [index.name for index in index_client.list_indexes()]
    if index_name in index_names:
        logging.info(f"Index {index_name} already exists, not re-creating")
    else:
        logging.info(f"Creating index: {index_name}")
        
        # Algorithm, vectorizer, and profile names based on sample.json
        algorithm_name = f"{index_name}-algorithm"
        vectorizer_name = f"{index_name}-azureOpenAi-text-vectorizer"
        profile_name = f"{index_name}-azureOpenAi-text-profile"
        semantic_config_name = f"{index_name}-semantic-configuration"

        index_client.create_or_update_index(
            SearchIndex(
                name=index_name,
                fields=[
                    SearchableField(name="chunk_id", key=True, analyzer_name="keyword", sortable=True),
                    SimpleField(name="parent_id", type=SearchFieldDataType.String, filterable=True),
                    SearchableField(name="title"),
                    SearchableField(name="chunk"),
                    # Add header fields due to Document Intelligence Layout processing
                    SearchableField(name="header_1"),
                    SearchableField(name="header_2"),
                    SearchableField(name="header_3"),
                    SimpleField(name="source_page", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
                    SearchField(
                        name="text_vector", 
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        vector_search_dimensions=azure_openai_embeddings_dimensions,
                        vector_search_profile_name=profile_name,
                        stored=True,
                        hidden=False)
                ],
                vector_search=VectorSearch(
                    algorithms=[
                        HnswAlgorithmConfiguration(
                            name=algorithm_name, 
                            parameters=HnswParameters(
                                metric=VectorSearchAlgorithmMetric.COSINE,
                                m=4,
                                ef_construction=400,
                                ef_search=500
                            )
                        )
                    ],
                    vectorizers=[
                        AzureOpenAIVectorizer(
                            vectorizer_name=vectorizer_name,
                            kind="azureOpenAi",
                            parameters=AzureOpenAIVectorizerParameters(
                                resource_url=azure_openai_embedding_endpoint,
                                auth_identity=SearchIndexerDataUserAssignedIdentity(resource_id=uami_id),
                                deployment_name=azure_openai_embedding_deployment,
                                model_name=azure_openai_embedding_model
                            )
                        )
                    ],
                    profiles=[
                        VectorSearchProfile(
                            name=profile_name, 
                            algorithm_configuration_name=algorithm_name, 
                            vectorizer_name=vectorizer_name
                        )
                    ]
                ),
                semantic_search=SemanticSearch(
                    configurations=[
                        SemanticConfiguration(
                            name=semantic_config_name,
                            prioritized_fields=SemanticPrioritizedFields(
                                title_field=SemanticField(field_name="title"), 
                                content_fields=[
                                    SemanticField(field_name="chunk")
                                ],
                                keywords_fields=[]
                            )
                        )
                    ],
                    default_configuration_name=semantic_config_name
                )
            )
        )
    # step 2.5: Create the skillset if it doesn't exist
    ai_services_key = os.environ.get('AZURE_AI_SERVICES_KEY', '')
    ai_services_endpoint = os.environ.get('AZURE_AI_FOUNDRY_ENDPOINT', '')
    
    # Check if the AI Services Key is a Key Vault reference and resolve it
    if ai_services_key and ai_services_key.startswith('@Microsoft.KeyVault'):
        logging.info("Resolving AI Service Key from Key Vault")
        ai_services_key = get_keyvault_secret(azure_credential, ai_services_key)
    
    logging.info(f"Creating skillset: {index_name}")
    skillset_name = f"{index_name}-skillset"
    indexer_client.create_or_update_skillset(
        skillset=SearchIndexerSkillset(
            name=skillset_name,
            description="Skillset to chunk documents and generating embeddings",  
            skills=[
                DocumentIntelligenceLayoutSkill(
                    name="document-layout-skill",
                    description="Layout skill to read documents",
                    context="/document",
                    output_mode="oneToMany",
                    markdown_header_depth="h3",
                    inputs=[InputFieldMappingEntry(name="file_data", source="/document/file_data")],
                    outputs=[OutputFieldMappingEntry(name="markdown_document", target_name="markdownDocument")],
                ),
                SplitSkill(
                    name="split-skill",
                    description="Split skill to chunk documents",  
                    text_split_mode="pages",
                    context="/document/markdownDocument/*",
                    maximum_page_length=2000,
                    page_overlap_length=500,
                    inputs=[InputFieldMappingEntry(name="text", source="/document/markdownDocument/*/content")],
                    outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")]),
                AzureOpenAIEmbeddingSkill(
                    name="azure-openai-embedding-skill",
                    description="Skill to generate embeddings via Azure OpenAI",  
                    context="/document/markdownDocument/*/pages/*",
                    resource_url=azure_openai_embedding_endpoint,
                    auth_identity=SearchIndexerDataUserAssignedIdentity(resource_id=uami_id),
                    deployment_name=azure_openai_embedding_deployment,
                    model_name=azure_openai_embedding_model,
                    dimensions=azure_openai_embeddings_dimensions,
                    inputs=[InputFieldMappingEntry(name="text", source="/document/markdownDocument/*/pages/*")],
                    outputs=[OutputFieldMappingEntry(name="embedding", target_name="text_vector")])
            ],
            index_projection=SearchIndexerIndexProjection(
                selectors=[
                    SearchIndexerIndexProjectionSelector(
                        target_index_name=index_name,
                        parent_key_field_name="parent_id",
                        source_context="/document/markdownDocument/*/pages/*",
                        mappings=[
                            InputFieldMappingEntry(name="chunk", source="/document/markdownDocument/*/pages/*"),
                            InputFieldMappingEntry(name="text_vector", source="/document/markdownDocument/*/pages/*/text_vector"),
                            InputFieldMappingEntry(name="title", source="/document/metadata_storage_name"),
                            # Add mappings for header fields
                            InputFieldMappingEntry(name="header_1", source="/document/markdownDocument/*/sections/h1"),
                            InputFieldMappingEntry(name="header_2", source="/document/markdownDocument/*/sections/h2"),
                            InputFieldMappingEntry(name="header_3", source="/document/markdownDocument/*/sections/h3"),
                        ]
                    )
                ],
                parameters=SearchIndexerIndexProjectionsParameters(
                    projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
                )
            ),
            cognitive_services_account=AIServicesAccountKey(
                key=ai_services_key,
                subdomain_url=ai_services_endpoint
                ) if ai_services_key else
                        AIServicesAccountIdentity(
                            identity=SearchIndexerDataUserAssignedIdentity(resource_id=uami_id),
                            subdomain_url=ai_services_endpoint
                        ),
            )
            )

    # Step 3: Create the indexer if it doesn't exist
    indexers = indexer_client.get_indexers()
    if f"{index_name}-indexer" in [indexer.name for indexer in indexers]:
        logging.info(f"Indexer {index_name}-indexer already exists, not re-creating")
    else:
        indexer_client.create_or_update_indexer(
            indexer=SearchIndexer(
                name=f"{index_name}-indexer" ,
                description="Indexer to index documents and generate embeddings",
                data_source_name=data_source.name,
                skillset_name=skillset_name,
                target_index_name=index_name,        
                parameters=IndexingParameters(
                    configuration=IndexingParametersConfiguration(
                        allow_skillset_to_read_file_data=True,
                        query_timeout=None)
                        )
            )
        )


def upload_documents(azure_credential, source_folder, indexer_name, azure_search_endpoint, azure_storage_endpoint, azure_storage_container):
    indexer_client = SearchIndexerClient(azure_search_endpoint, azure_credential)
    # Upload the documents in /data folder to the blob storage container
    blob_client = BlobServiceClient(
        account_url=azure_storage_endpoint, credential=azure_credential,
        max_single_put_size=4 * 1024 * 1024
    )
    container_client = blob_client.get_container_client(azure_storage_container)
    if not container_client.exists():
        container_client.create_container()
    existing_blobs = [blob.name for blob in container_client.list_blobs()]

    # Open each file in /data folder
    for file in os.scandir(source_folder):
        with open(file.path, "rb") as opened_file:
            filename = os.path.basename(file.path)
            # Check if blob already exists
            if filename in existing_blobs:
                logging.info("Blob already exists, skipping file: %s", filename)
            else:
                logging.info("Uploading blob for file: %s", filename)
                blob_client = container_client.upload_blob(filename, opened_file, overwrite=True)

    # Start the indexer
    try:
        indexer_client.run_indexer(indexer_name)
        logging.info("Indexer started. Any unindexed blobs should be indexed in a few minutes, check the Azure Portal for status.")
    except ResourceExistsError:
        logging.info("Indexer already running, not starting again")
