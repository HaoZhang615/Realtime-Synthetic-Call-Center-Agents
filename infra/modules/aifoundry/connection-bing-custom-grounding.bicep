// Grounding with Bing Custom Search Connection for AI Foundry
// This module creates a connection between an existing Bing Custom Search (Grounding) resource and the AI Foundry Project

@description('AI Foundry account name')
param aiFoundryName string

@description('Resource ID of the Bing Custom Search (Grounding) service')
param bingCustomSearchServiceId string

@description('Name of the Bing Custom Search (Grounding) service')
param bingCustomSearchServiceName string

@secure()
@description('API key for the Bing Custom Search service')
param apiKey string

@description('Optional custom search configuration ID (if applicable)')
param customConfigId string = ''

// Reference to your existing Azure AI Foundry account
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiFoundryName
  scope: resourceGroup()
}

// Creates the Azure AI Foundry connection to your Bing Custom Search Grounding resource
resource bingCustomGroundingConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  // Connection names must be alphanumeric; remove dashes/underscores from the service name
  name: replace(replace(bingCustomSearchServiceName, '-', ''), '_', '')
  parent: aiFoundry
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/v7.0/custom/search'
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: apiKey
    }
    metadata: {
      ApiType: 'Azure'
      Type: 'bing_custom_search' // Keep consistent with Bing grounding connection type
      ResourceId: bingCustomSearchServiceId
      Location: 'global'
      CustomConfigId: customConfigId
    }
  }
}

// Outputs
output bingCustomGroundingConnectionName string = bingCustomGroundingConnection.name
output bingCustomGroundingConnectionId string = bingCustomGroundingConnection.id
output endpoint string = 'https://api.bing.microsoft.com/v7.0/custom/search'
