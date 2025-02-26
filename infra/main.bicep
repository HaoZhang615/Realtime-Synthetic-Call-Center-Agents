targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources (filtered on available regions for Azure Open AI Service).')
@allowed([
  'eastus2'
  'swedencentral'
])
param location string
param searchServiceLocation string = 'eastus'
param appExists bool

@description('Whether the deployment is running on GitHub Actions')
param runningOnGh string = ''

@description('Whether the deployment is running on Azure DevOps Pipeline')
param runningOnAdo string = ''

@description('Id of the user or app to assign application roles')
param principalId string = ''
var principalType = empty(runningOnGh) && empty(runningOnAdo) ? 'User' : 'ServicePrincipal'

param openAiRealtimeName string = ''
param openAiRealtimeKey string = ''

param searchIndexName string = 'documents'

@description('Name of the resource group. Leave blank to use default naming conventions.')
param resourceGroupName string = ''

@description('Tags to be applied to resources.')
param tags object = { 'azd-env-name': environmentName }

// Add new parameters for Bing Search API to replace dynamic loadJsonContent calls
@secure()
@description('Bing Search API Key')
param bingSearchApiKey string

@description('Bing Search API Endpoint')
param bingSearchApiEndpoint string = 'https://api.bing.microsoft.com/v7.0/search'

// Load abbreviations from JSON file
var abbrs = loadJsonContent('./abbreviations.json')
// Generate a unique token for resources
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Organize resources in a resource group
resource resGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

// ------------------------
// [ User Assigned Identity for App to avoid circular dependency ]
module appIdentity './modules/app/identity.bicep' = {
  name: 'uami'
  scope: resGroup
  params: {
    location: location
    identityName: 'app-${resourceToken}'
  }
}

// ------------------------
// [ Array of OpenAI Model deployments ]
param aoaiGpt4oRealtimeModelName string = 'gpt-4o-mini-realtime-preview'
param aoaiGpt4ModelVersion string = '2024-12-17'
param aoaiGpt4oMiniModelName string = 'gpt-4o-mini'
param aoaiGpt4oMiniModelVersion string = '2024-07-18'
param embedModel string = 'text-embedding-3-large'

var embeddingDeployment = [
  {
    name: embedModel
    model: {
      format: 'OpenAI'
      name: embedModel
      version: '1'
    }
    sku: { 
      name: 'Standard' 
      capacity: 50 }
  }
]

var realtimeDeployment =    [{
    name: aoaiGpt4oRealtimeModelName
    model: {
      format: 'OpenAI'
      name: aoaiGpt4oRealtimeModelName
      version: aoaiGpt4ModelVersion
    }
    sku: { 
      name: 'GlobalStandard'
      capacity:  1
    }
  }]

var gpt4ominiDeployment =    [{
    name: aoaiGpt4oMiniModelName
    model: {
      format: 'OpenAI'
      name: aoaiGpt4oMiniModelName
      version: aoaiGpt4oMiniModelVersion
    }
    sku: { 
      name: 'GlobalStandard'
      capacity:  50
    }
  }]

var openAiDeployments = concat(realtimeDeployment, gpt4ominiDeployment, embeddingDeployment)

module openAi 'br/public:avm/res/cognitive-services/account:0.8.0' = {
  name: 'openai'
  scope: resGroup
  params: {
    name: 'oai-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'aoai-${tags['azd-env-name']}' })
    kind: 'OpenAI'
    customSubDomainName: 'oai-${resourceToken}'
    sku: 'S0'
    deployments: openAiDeployments
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {}
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        principalId: principalId
        principalType: principalType
      }
    ]
  }
}

var logAnalyticsName = '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
module monitoring 'modules/monitoring/monitor.bicep' = {
  name: 'monitor'
  scope: resGroup
  params: {
    logAnalyticsName: logAnalyticsName
    resourceToken: resourceToken
    tags: tags
  }
}

module registry 'modules/app/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    identityName: appIdentity.outputs.name
    tags: tags
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
  }
  scope: resGroup
}

module cosmosdb 'modules/cosmos/cosmos.bicep' = {
  name: 'cosmosdb'
  params: {
    cosmosDbAccountName: 'cosmos${resourceToken}'
    location: location
    identityName: appIdentity.outputs.name
    principalId: principalId
    principalType: principalType
    tags: tags
  }
  scope: resGroup
}

// Microsoft.Web/connections resource to Outlook 365
module office365Connection 'br/public:avm/res/web/connection:0.4.1' = {
  name: 'office365'
  scope: resGroup
  params: {
    name: 'office365'
    api: {
      id: '/subscriptions/${subscription().subscriptionId}/providers/Microsoft.Web/locations/${location}/managedApis/office365'
    }
    displayName: 'office365'
  }
}

module sendEmailLogic 'br/public:avm/res/logic/workflow:0.4.0' = {
  name: 'sendEmailLogic'
  scope: resGroup
  params: {
    name: '${abbrs.logicWorkflows}sendemail-${resourceToken}'
    location: resGroup.location
    managedIdentities: { userAssignedResourceIds: [appIdentity.outputs.identityId] }
    diagnosticSettings: [
      {
        name: 'customSetting'
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
        workspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceId
      }
    ]
    workflowActions: loadJsonContent('./modules/logicapp/send_email.actions.json')
    workflowTriggers: loadJsonContent('./modules/logicapp/send_email.triggers.json')
    workflowParameters: loadJsonContent('./modules/logicapp/send_email.parameters.json')
    definitionParameters: {
      '$connections': {
        value: {
          office365: {
            id: '/subscriptions/${subscription().subscriptionId}/providers/Microsoft.Web/locations/${location}/managedApis/office365'
            connectionId: office365Connection.outputs.resourceId
            connectionName: office365Connection.name
          }
        }
      }
    }
  }
}

module sendMailUrl 'modules/logicapp/retrieve_http_trigger.bicep' = {
  name: 'sendMailUrl'
  scope: resGroup
  params: {
    logicAppName: '${abbrs.logicWorkflows}sendemail-${resourceToken}'
    triggerName: 'When_a_HTTP_request_is_received'
  }
  dependsOn: [sendEmailLogic]
}

var openAiEndpoint = !empty(openAiRealtimeName)
  ? 'https://${openAiRealtimeName}.openai.azure.com'
  : openAi.outputs.endpoint

module frontendApp 'modules/app/containerapp.bicep' = {
  name: 'frontend'
  scope: resGroup
  params: {
    appName: '${abbrs.appContainerApps}frontend-${resourceToken}'
    serviceName: 'frontend'  // Changed from 'app' to 'frontend'
    location: location
    tags: tags
    logAnalyticsWorkspaceName: logAnalyticsName
    identityId: appIdentity.outputs.identityId
    containerRegistryName: registry.outputs.name
    exists: appExists
    targetPort: 80
    env: union({
      AZURE_CLIENT_ID: appIdentity.outputs.clientId
      AZURE_USER_ASSIGNED_IDENTITY_ID: appIdentity.outputs.identityId
      APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.appInsightsConnectionString
      AZURE_OPENAI_ENDPOINT: openAiEndpoint
      AZURE_OPENAI_GPT4o_REALTIME_DEPLOYMENT: aoaiGpt4oRealtimeModelName
      AZURE_SEARCH_ENDPOINT: 'https://${searchService.outputs.name}.search.windows.net'
      AZURE_SEARCH_INDEX: searchIndexName
      SEND_EMAIL_LOGIC_APP_URL: sendMailUrl.outputs.url
      COSMOSDB_ENDPOINT: cosmosdb.outputs.cosmosDbEndpoint
      COSMOSDB_DATABASE: cosmosdb.outputs.cosmosDbDatabase
      COSMOSDB_AIConversations_CONTAINER: cosmosdb.outputs.cosmosDbAIConversationsContainer
      COSMOSDB_Customer_CONTAINER: cosmosdb.outputs.cosmosDbCustomerContainer
      COSMOSDB_HumanConversations_CONTAINER: cosmosdb.outputs.cosmosDbHumanConversationsContainer
      COSMOSDB_Product_CONTAINER: cosmosdb.outputs.cosmosDbProductContainer
      COSMOSDB_Purchases_CONTAINER: cosmosdb.outputs.cosmosDbPurchasesContainer
      BING_SEARCH_API_ENDPOINT: bingSearchApiEndpoint
      BING_SEARCH_API_KEY: bingSearchApiKey
    },
    empty(openAiRealtimeName) ? {} : {
      AZURE_OPENAI_API_KEY: openAiRealtimeKey
    })
  }
}

module backendApp 'modules/app/containerapp.bicep' = {
  name: 'backend'
  scope: resGroup
  params: {
    appName: '${abbrs.appContainerApps}backend-${resourceToken}'
    serviceName: 'backend'
    location: location
    tags: tags
    logAnalyticsWorkspaceName: logAnalyticsName
    identityId: appIdentity.outputs.identityId
    containerRegistryName: registry.outputs.name
    exists: appExists
    targetPort: 80  // Updated targetPort to 80 to match container listening port
    env: union({
      AZURE_CLIENT_ID: appIdentity.outputs.clientId
      AZURE_USER_ASSIGNED_IDENTITY_ID: appIdentity.outputs.identityId
      APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.appInsightsConnectionString
      AZURE_OPENAI_ENDPOINT: openAiEndpoint
      AZURE_OPENAI_EMBEDDING_ENDPOINT: openAiEndpoint
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embedModel
      AZURE_OPENAI_EMBEDDING_MODEL: embedModel
      AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT: aoaiGpt4oMiniModelName
      AZURE_SEARCH_ENDPOINT: 'https://${searchService.outputs.name}.search.windows.net'
      AZURE_SEARCH_INDEX: searchIndexName
      AZURE_STORAGE_ENDPOINT: 'https://${storage.outputs.name}.blob.core.windows.net'
      AZURE_STORAGE_CONNECTION_STRING: 'ResourceId=/subscriptions/${subscription().subscriptionId}/resourceGroups/${resGroup.name}/providers/Microsoft.Storage/storageAccounts/${storage.outputs.name}'
      AZURE_STORAGE_CONTAINER: storageContainerName
      COSMOSDB_ENDPOINT: cosmosdb.outputs.cosmosDbEndpoint
      COSMOSDB_DATABASE: cosmosdb.outputs.cosmosDbDatabase
      COSMOSDB_AIConversations_CONTAINER: cosmosdb.outputs.cosmosDbAIConversationsContainer
      COSMOSDB_Customer_CONTAINER: cosmosdb.outputs.cosmosDbCustomerContainer
      COSMOSDB_HumanConversations_CONTAINER: cosmosdb.outputs.cosmosDbHumanConversationsContainer
      COSMOSDB_Product_CONTAINER: cosmosdb.outputs.cosmosDbProductContainer
      COSMOSDB_Purchases_CONTAINER: cosmosdb.outputs.cosmosDbPurchasesContainer
    },
    empty(openAiRealtimeName) ? {} : {
      AZURE_OPENAI_API_KEY: openAiRealtimeKey
    })
  }
}

module searchService 'br/public:avm/res/search/search-service:0.7.1' = {
  name: 'search-service'
  scope: resGroup
  params: {
    name: 'aisearch-${resourceToken}'
    location: !empty(searchServiceLocation) ? searchServiceLocation : location
    tags: tags
    disableLocalAuth: true
    sku: 'standard'
    replicaCount: 1
    semanticSearch: 'standard'
    // An outbound managed identity is required for integrated vectorization to work,
    // and is only supported on non-free tiers:
    managedIdentities: { userAssignedResourceIds: [appIdentity.outputs.identityId] }
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Search Index Data Reader'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Search Index Data Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Search Service Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Search Index Data Reader'
        principalId: principalId
        principalType: principalType
      }
      {
        roleDefinitionIdOrName: 'Search Index Data Contributor'
        principalId: principalId
        principalType: principalType
      }
      {
        roleDefinitionIdOrName: 'Search Service Contributor'
        principalId: principalId
        principalType: principalType
      }
    ]
  }
}

var storageContainerName = 'documents'
module storage 'br/public:avm/res/storage/storage-account:0.9.1' = {
  name: 'storage'
  scope: resGroup
  params: {
    name: '${abbrs.storageStorageAccounts}${resourceToken}'
    location: resGroup.location
    tags: tags
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    publicNetworkAccess: 'Enabled' // Necessary for uploading documents to storage container
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    blobServices: {
      deleteRetentionPolicyDays: 2
      deleteRetentionPolicyEnabled: true
      containers: [
        {
          name: storageContainerName
          publicAccess: 'None'
        }
      ]
    }
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Storage Blob Data Reader'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      // For uploading documents to storage container:
      {
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Storage Blob Data Reader'
        principalId: principalId
        principalType: principalType
      }
      {
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalId: principalId
        principalType: principalType
      }
    ]
  }
}

// OUTPUTS will be saved in azd env for later use
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resGroup.name
output AZURE_USER_ASSIGNED_IDENTITY_ID string = appIdentity.outputs.identityId

output AZURE_OPENAI_ENDPOINT string = openAiEndpoint
output AZURE_OPENAI_EMBEDDING_ENDPOINT string = openAi.outputs.endpoint
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embedModel
output AZURE_OPENAI_EMBEDDING_MODEL string = embedModel
output AZURE_OPENAI_GPT4o_REALTIME_DEPLOYMENT string = aoaiGpt4oRealtimeModelName
output AZURE_OPENAI_GPT4o_MINI_DEPLOYMENT string = aoaiGpt4oMiniModelName

output AZURE_SEARCH_ENDPOINT string = 'https://${searchService.outputs.name}.search.windows.net'
output AZURE_SEARCH_INDEX string = searchIndexName

output AZURE_STORAGE_ENDPOINT string = 'https://${storage.outputs.name}.blob.core.windows.net'
output AZURE_STORAGE_ACCOUNT string = storage.outputs.name
output AZURE_STORAGE_CONNECTION_STRING string = 'ResourceId=/subscriptions/${subscription().subscriptionId}/resourceGroups/${resGroup.name}/providers/Microsoft.Storage/storageAccounts/${storage.outputs.name}'
output AZURE_STORAGE_CONTAINER string = storageContainerName
output AZURE_STORAGE_RESOURCE_GROUP string = resGroup.name

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer

output SEND_EMAIL_LOGIC_APP_URL string = sendMailUrl.outputs.url

output COSMOSDB_ENDPOINT string = cosmosdb.outputs.cosmosDbEndpoint
output COSMOSDB_DATABASE string = cosmosdb.outputs.cosmosDbDatabase
output COSMOSDB_AIConversations_CONTAINER string = cosmosdb.outputs.cosmosDbAIConversationsContainer
output COSMOSDB_Customer_CONTAINER string = cosmosdb.outputs.cosmosDbCustomerContainer
output COSMOSDB_HumanConversations_CONTAINER string = cosmosdb.outputs.cosmosDbHumanConversationsContainer
output COSMOSDB_Product_CONTAINER string = cosmosdb.outputs.cosmosDbProductContainer
output COSMOSDB_Purchases_CONTAINER string = cosmosdb.outputs.cosmosDbPurchasesContainer
output COSMOSDB_ProductUrl_CONTAINER string = cosmosdb.outputs.cosmosDbProductUrlContainer

output BING_SEARCH_API_ENDPOINT string = bingSearchApiEndpoint
