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
param searchServiceLocation string = ''
param appExists bool

@description('Whether the deployment is running on GitHub Actions')
param runningOnGh string = ''

@description('Whether the deployment is running on Azure DevOps Pipeline')
param runningOnAdo string = ''

@description('Deploy with Zero Trust architecture (private networking, VNet integration, private endpoints)')
param enableZeroTrust bool

@description('Id of the user or app to assign application roles')
param principalId string = ''
var principalType = empty(runningOnGh) && empty(runningOnAdo) ? 'User' : 'ServicePrincipal'

param openAiRealtimeName string = ''

param searchIndexName string = 'documents'

@description('Name of the resource group. Leave blank to use default naming conventions.')
param resourceGroupName string = ''

@description('Tags to be applied to resources.')
param tags object = { 'azd-env-name': environmentName }

@maxLength(60)
@description('Name of the container apps environment to deploy. If not specified, a name will be generated. The maximum length is 60 characters.')
param containerAppsEnvironmentName string = ''

// Load abbreviations from JSON file
var abbrs = loadJsonContent('./abbreviations.json')
// Generate a unique token for resources
var resourceToken = toLower(uniqueString(subscription().id, location, environmentName))

var _containerAppsEnvironmentName = !empty(containerAppsEnvironmentName)
  ? containerAppsEnvironmentName
  : take('${abbrs.appManagedEnvironments}${resourceToken}', 60)
  
  // Organize resources in a resource group
resource resGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

// Create VNet and subnets (only for Zero Trust deployment)
module vnet './modules/network/vnet.bicep' = if (enableZeroTrust) {
  name: 'vnet'
  scope: resGroup
  params: {
    vnetName: 'vnet-${resourceToken}'
    location: location
    tags: tags
  }
}

// Create container apps environment for standard deployment (no VNet integration)
module containerAppsEnvironment './modules/app/containerappenv.bicep' = if (!enableZeroTrust) {
  name: 'containerAppsEnvironment'
  params: {
    envName: _containerAppsEnvironmentName
    location: location
    tags: tags
    logAnalyticsWorkspaceName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    appSubnetId: ''
  }
  scope: resGroup
  dependsOn: [
    monitoring  // ✅ ADD THIS - Wait for Log Analytics to be created
  ]
}

// Create container apps environment for zero trust deployment (with VNet integration)
module containerAppsEnvironmentZeroTrust './modules/app/containerappenv.bicep' = if (enableZeroTrust) {
  name: 'containerAppsEnvironmentZeroTrust'
  params: {
    envName: _containerAppsEnvironmentName
    location: location
    tags: tags
    logAnalyticsWorkspaceName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    appSubnetId: vnet!.outputs.appSubnetId
  }
  scope: resGroup
  dependsOn: [
    monitoring  // ✅ ADD THIS - Wait for Log Analytics to be created
  ]
}

// Private Endpoints for backend services (only for Zero Trust deployment)
module storagePrivateEndpoint './modules/network/private-endpoint.bicep' = if (enableZeroTrust) {
  name: 'storage-pe'
  scope: resGroup
  params: {
    name: 'storage-pe-${resourceToken}'
    location: location
    subnetId: vnet!.outputs.backendSubnetId
    groupId: 'blob'
    privateLinkResourceId: storage.outputs.resourceId
    tags: tags
  }
}

module cosmosPrivateEndpoint './modules/network/private-endpoint.bicep' = if (enableZeroTrust) {
  name: 'cosmos-pe'
  scope: resGroup
  params: {
    name: 'cosmos-pe-${resourceToken}'
    location: location
    subnetId: vnet!.outputs.backendSubnetId
    groupId: 'Sql'
    privateLinkResourceId: cosmosdb.outputs.cosmosDbAccountId
    tags: tags
  }
}

module searchPrivateEndpoint './modules/network/private-endpoint.bicep' = if (enableZeroTrust) {
  name: 'search-pe'
  scope: resGroup
  params: {
    name: 'search-pe-${resourceToken}'
    location: location
    subnetId: vnet!.outputs.backendSubnetId
    groupId: 'searchService'
    privateLinkResourceId: searchService.outputs.resourceId
    tags: tags
  }
}

module keyVaultPrivateEndpoint './modules/network/private-endpoint.bicep' = if (enableZeroTrust) {
  name: 'keyvault-pe'
  scope: resGroup
  params: {
    name: 'keyvault-pe-${resourceToken}'
    location: location
    subnetId: vnet!.outputs.backendSubnetId
    groupId: 'vault'
    privateLinkResourceId: keyVault.outputs.resourceId
    tags: tags
  }
}

module aiServicesPrivateEndpoint './modules/network/private-endpoint.bicep' = if (enableZeroTrust) {
  name: 'aiservices-pe'
  scope: resGroup
  params: {
    name: 'aiservices-pe-${resourceToken}'
    location: location
    subnetId: vnet!.outputs.backendSubnetId
    groupId: 'account'
    privateLinkResourceId: account.outputs.resourceId
    tags: tags
  }
}

// Private DNS Zones for proper DNS resolution (only for Zero Trust deployment)
module cosmosPrivateDnsZone './modules/network/private-dns-zone.bicep' = if (enableZeroTrust) {
  name: 'cosmos-dns-zone'
  scope: resGroup
  params: {
    privateEndpointId: cosmosPrivateEndpoint!.outputs.id
    privateDnsZoneName: 'privatelink.documents.azure.com'
    vnetId: vnet!.outputs.vnetId
    tags: tags
  }
}

module storagePrivateDnsZone './modules/network/private-dns-zone.bicep' = if (enableZeroTrust) {
  name: 'storage-dns-zone'
  scope: resGroup
  params: {
    privateEndpointId: storagePrivateEndpoint!.outputs.id
    privateDnsZoneName: 'privatelink.blob.${environment().suffixes.storage}'
    vnetId: vnet!.outputs.vnetId
    tags: tags
  }
}

module searchPrivateDnsZone './modules/network/private-dns-zone.bicep' = if (enableZeroTrust) {
  name: 'search-dns-zone'
  scope: resGroup
  params: {
    privateEndpointId: searchPrivateEndpoint!.outputs.id
    privateDnsZoneName: 'privatelink.search.windows.net'
    vnetId: vnet!.outputs.vnetId
    tags: tags
  }
}

module keyVaultPrivateDnsZone './modules/network/private-dns-zone.bicep' = if (enableZeroTrust) {
  name: 'keyvault-dns-zone'
  scope: resGroup
  params: {
    privateEndpointId: keyVaultPrivateEndpoint!.outputs.id
    privateDnsZoneName: 'privatelink.vaultcore.azure.net'
    vnetId: vnet!.outputs.vnetId
    tags: tags
  }
}



module aiServicesPrivateDnsZone './modules/network/private-dns-zone.bicep' = if (enableZeroTrust) {
  name: 'aiservices-dns-zone'
  scope: resGroup
  params: {
    privateEndpointId: aiServicesPrivateEndpoint!.outputs.id
    privateDnsZoneName: 'privatelink.cognitiveservices.azure.com'
    vnetId: vnet!.outputs.vnetId
    tags: tags
  }
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
// [ Array of AI Services Model deployments ]
param aoaiGptRealtimeModelName string = 'gpt-realtime'
param aoaiGptRealtimeModelVersion string = '2025-08-28'
param aoaiGptRealtimeMiniModelName string = 'gpt-realtime-mini'
param aoaiGptRealtimeMiniModelVersion string = '2025-10-06'
param aoaiGptChatModelName string = 'gpt-4.1-nano'
param aoaiGptChatModelVersion string = '2025-04-14'
param embedModel string = 'text-embedding-3-large'



// Add Key Vault to store secrets like Bing Search API Key
module keyVault 'br/public:avm/res/key-vault/vault:0.4.0' = {
  name: 'keyVault'
  scope: resGroup
  params: {
    name: 'kv-${resourceToken}'
    location: location
    enableRbacAuthorization: true
    publicNetworkAccess: enableZeroTrust ? 'Disabled' : 'Enabled'
    networkAcls: enableZeroTrust ? {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    } : {
      defaultAction: 'Allow'
    }
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Key Vault Secrets User'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Key Vault Secrets Officer'
        principalId: principalId
        principalType: principalType
      }
    ]
  }
}

param accounts_aiservice_ms_name string = ''
var _accounts_aiservice_ms_name = !empty(accounts_aiservice_ms_name) ? accounts_aiservice_ms_name : '${abbrs.cognitiveServicesAccounts}${resourceToken}'

// AI Services account with AI Foundry project management enabled
module account 'modules/ai/account.bicep' = {
  name: 'ai-services-account'
  scope: resGroup
  params: {
    accountName: _accounts_aiservice_ms_name
    location: location
    tags: tags
    deployments: [
      {
        name: aoaiGptRealtimeModelName
        model: {
          format: 'OpenAI'
          name: aoaiGptRealtimeModelName
          version: aoaiGptRealtimeModelVersion
        }
        sku: { 
          name: 'GlobalStandard'
          capacity: 1
        }
      }
      {
        name: aoaiGptRealtimeMiniModelName
        model: {
          format: 'OpenAI'
          name: aoaiGptRealtimeMiniModelName
          version: aoaiGptRealtimeMiniModelVersion
        }
        sku: { 
          name: 'GlobalStandard'
          capacity: 10
        }
      }
      {
        name: aoaiGptChatModelName
        model: {
          format: 'OpenAI'
          name: aoaiGptChatModelName
          version: aoaiGptChatModelVersion
        }
        sku: { 
          name: 'GlobalStandard'
          capacity: 50
        }
      }
      {
        name: embedModel
        model: {
          format: 'OpenAI'
          name: embedModel
          version: '1'
        }
        sku: { 
          name: 'Standard' 
          capacity: 50
        }
      }
    ]
    keyVaultResourceId: keyVault.outputs.resourceId
    appIdentityPrincipalId: appIdentity.outputs.principalId
    principalId: principalId
    principalType: principalType
  }
}

// ========================
// AI Foundry Resources
// ========================

// Deploy Bing Search for Grounding
module bingSearch 'modules/bing/grounding-bing-search.bicep' = {
  name: 'bing-search'
  scope: resGroup
  params: {
    bingGroundingServiceName: 'bing-${resourceToken}'
    tags: tags
    skuName: 'G1'
    statisticsEnabled: false
  }
}

// Deploy AI Foundry Project (using the consolidated AI Services account)
module aiFoundryProject 'modules/ai/project.bicep' = {
  name: 'ai-foundry-project'
  scope: resGroup
  params: {
    accountName: account.outputs.accountName
    projectName: 'project-${resourceToken}'
    location: location
    projectDescription: 'AI Foundry project for realtime call center agents with Bing Search'
    projectDisplayName: 'Call Center Agents Project'
    tags: tags
  }
}

// Create connection between AI Foundry Account and Bing Search
module bingConnection 'modules/ai/bing-connection.bicep' = {
  name: 'bing-connection'
  scope: resGroup
  params: {
    accountName: account.outputs.accountName
    bingSearchName: bingSearch.outputs.bingGroundingServiceName
  }
}

// Grant backend app identity access to AI Foundry Project
module aiFoundryAppRbac 'modules/ai/rbac.bicep' = {
  name: 'ai-foundry-app-rbac'
  scope: resGroup
  params: {
    principalId: appIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    projectResourceId: aiFoundryProject.outputs.projectId
  }
}

// Also grant user access for testing
module aiFoundryUserRbac 'modules/ai/rbac.bicep' = if (!empty(principalId)) {
  name: 'ai-foundry-user-rbac'
  scope: resGroup
  params: {
    principalId: principalId
    principalType: principalType
    projectResourceId: aiFoundryProject.outputs.projectId
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
    enableZeroTrust: enableZeroTrust
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

var FoundryEndpoint = account.outputs.endpoint

module frontendApp 'modules/app/containerapp.bicep' = {
  name: 'frontend'
  scope: resGroup
  params: {
    appName: '${abbrs.appContainerApps}frontend-${resourceToken}'
    serviceName: 'frontend'
    location: location
    tags: tags
    identityId: appIdentity.outputs.identityId
    containerAppsEnvironmentId: enableZeroTrust ? containerAppsEnvironmentZeroTrust!.outputs.id : containerAppsEnvironment!.outputs.id
    containerRegistryName: registry.outputs.name
    exists: appExists
    targetPort: 80
    env: union({
      // Frontend runtime configuration - point to backend URL
      VITE_API_BASE: 'https://${abbrs.appContainerApps}backend-${resourceToken}.${enableZeroTrust ? containerAppsEnvironmentZeroTrust!.outputs.defaultDomain : containerAppsEnvironment!.outputs.defaultDomain}'
      VITE_REALTIME_API_BASE: 'https://${abbrs.appContainerApps}backend-${resourceToken}.${enableZeroTrust ? containerAppsEnvironmentZeroTrust!.outputs.defaultDomain : containerAppsEnvironment!.outputs.defaultDomain}'
      // Azure service configuration (for reference)
      AZURE_CLIENT_ID: appIdentity.outputs.clientId
      AZURE_USER_ASSIGNED_IDENTITY_ID: appIdentity.outputs.identityId
      APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.appInsightsConnectionString
      AZURE_AI_FOUNDRY_ENDPOINT: FoundryEndpoint
      AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT: aoaiGptRealtimeModelName
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
      COSMOSDB_ProductUrl_CONTAINER: cosmosdb.outputs.cosmosDbProductUrlContainer
    }, {})
    // Key Vault secrets for frontend (if any needed in future)
    keyVaultSecrets: {}
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
    identityId: appIdentity.outputs.identityId
    containerAppsEnvironmentId: enableZeroTrust ? containerAppsEnvironmentZeroTrust!.outputs.id : containerAppsEnvironment!.outputs.id
    containerRegistryName: registry.outputs.name
    exists: appExists
    targetPort: 8000
    env: union({
      // CORS configuration - allow frontend origin
      FRONTEND_ORIGINS: 'https://${abbrs.appContainerApps}frontend-${resourceToken}.${enableZeroTrust ? containerAppsEnvironmentZeroTrust!.outputs.defaultDomain : containerAppsEnvironment!.outputs.defaultDomain},http://localhost:5173,http://localhost:5001,http://localhost:5000'
      // Azure service configuration
      AZURE_CLIENT_ID: appIdentity.outputs.clientId
      AZURE_USER_ASSIGNED_IDENTITY_ID: appIdentity.outputs.identityId
      APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.appInsightsConnectionString
      AZURE_AI_FOUNDRY_ENDPOINT: account.outputs.accountEndpoint
      AZURE_AI_FOUNDRY_PROJECT_ID: aiFoundryProject.outputs.projectId
      AZURE_AI_FOUNDRY_BING_CONNECTION_ID: bingConnection.outputs.connectionId
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embedModel
      AZURE_OPENAI_EMBEDDING_MODEL: embedModel
      AZURE_OPENAI_GPT_CHAT_DEPLOYMENT: aoaiGptChatModelName
      AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT: aoaiGptRealtimeModelName
      AZURE_SEARCH_ENDPOINT: 'https://${searchService.outputs.name}.search.windows.net'
      AZURE_SEARCH_INDEX: searchIndexName
      AZURE_STORAGE_ENDPOINT: storage.outputs.primaryBlobEndpoint
      AZURE_STORAGE_CONNECTION_STRING: 'ResourceId=/subscriptions/${subscription().subscriptionId}/resourceGroups/${resGroup.name}/providers/Microsoft.Storage/storageAccounts/${storage.outputs.name};'
      AZURE_STORAGE_CONTAINER: storageContainerName
      COSMOSDB_ENDPOINT: cosmosdb.outputs.cosmosDbEndpoint
      COSMOSDB_DATABASE: cosmosdb.outputs.cosmosDbDatabase
      COSMOSDB_AIConversations_CONTAINER: cosmosdb.outputs.cosmosDbAIConversationsContainer
      COSMOSDB_Customer_CONTAINER: cosmosdb.outputs.cosmosDbCustomerContainer
      COSMOSDB_HumanConversations_CONTAINER: cosmosdb.outputs.cosmosDbHumanConversationsContainer
      COSMOSDB_Product_CONTAINER: cosmosdb.outputs.cosmosDbProductContainer
      COSMOSDB_Purchases_CONTAINER: cosmosdb.outputs.cosmosDbPurchasesContainer
      COSMOSDB_ProductUrl_CONTAINER: cosmosdb.outputs.cosmosDbProductUrlContainer
    },
    empty(openAiRealtimeName) ? {} : {
      // Only include if using bring-your-own OpenAI key
    })
    // Key Vault secrets - these will be resolved by Container Apps
    keyVaultSecrets: {
      AZURE_AI_SERVICES_KEY: 'https://${keyVault.outputs.name}${environment().suffixes.keyvaultDns}/secrets/${_accounts_aiservice_ms_name}-accessKey1'
      AZURE_OPENAI_API_KEY: 'https://${keyVault.outputs.name}${environment().suffixes.keyvaultDns}/secrets/${_accounts_aiservice_ms_name}-accessKey1'
    }
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
    publicNetworkAccess: enableZeroTrust ? 'Disabled' : 'Enabled'
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
    publicNetworkAccess: enableZeroTrust ? 'Disabled' : 'Enabled'
    networkAcls: enableZeroTrust ? {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    } : {
      defaultAction: 'Allow'
    }
    allowBlobPublicAccess: false
    allowSharedKeyAccess: enableZeroTrust ? false : true
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
output AZURE_CLIENT_ID string = appIdentity.outputs.clientId
output AZURE_RESOURCE_GROUP string = resGroup.name
output RESOURCE_GROUP_ID string = resGroup.id
output AZURE_USER_ASSIGNED_IDENTITY_ID string = appIdentity.outputs.identityId

// AI Foundry outputs
output AZURE_AI_FOUNDRY_ENDPOINT string = account.outputs.accountEndpoint
output AZURE_AI_FOUNDRY_ACCOUNT_NAME string = account.outputs.accountName
output AZURE_AI_FOUNDRY_PROJECT_ID string = aiFoundryProject.outputs.projectId
output AZURE_AI_FOUNDRY_PROJECT_NAME string = aiFoundryProject.outputs.projectName
output AZURE_AI_FOUNDRY_BING_CONNECTION_ID string = bingConnection.outputs.connectionId
// Model deployment is now managed in the consolidated account
output AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT string = aoaiGptRealtimeModelName

// Azure OpenAI outputs (from original AI Services account)
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embedModel
output AZURE_OPENAI_EMBEDDING_MODEL string = embedModel
output AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT string = aoaiGptRealtimeModelName
output AZURE_OPENAI_GPT_CHAT_DEPLOYMENT string = aoaiGptChatModelName

output AZURE_SEARCH_ENDPOINT string = 'https://${searchService.outputs.name}.search.windows.net'
output AZURE_SEARCH_INDEX string = searchIndexName

output AZURE_STORAGE_ENDPOINT string = storage.outputs.primaryBlobEndpoint
output AZURE_STORAGE_ACCOUNT string = storage.outputs.name
output AZURE_STORAGE_CONNECTION_STRING string = 'ResourceId=/subscriptions/${subscription().subscriptionId}/resourceGroups/${resGroup.name}/providers/Microsoft.Storage/storageAccounts/${storage.outputs.name};'
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

output AZURE_AI_SERVICES_KEY string = '@Microsoft.KeyVault(SecretUri=https://${keyVault.outputs.name}.vault.azure.net/secrets/${_accounts_aiservice_ms_name}-accessKey1/)'
