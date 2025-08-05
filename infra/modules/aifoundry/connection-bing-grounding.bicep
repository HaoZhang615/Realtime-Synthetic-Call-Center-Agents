// Grounding with Bing Search Connection for AI Foundry
// This module creates a connection between an existing Bing Grounding resource and the AI Foundry Project

param aiFoundryName string
param bingGroundingServiceId string
param bingGroundingServiceName string
param apiKey string

// Refers to your existing Azure AI Foundry resource
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiFoundryName
  scope: resourceGroup()
}

// Creates the Azure Foundry connection to your Bing Grounding resource
resource bingGroundingConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: replace(replace(bingGroundingServiceName, '-', ''), '_', '')
  parent: aiFoundry
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: apiKey
    }
    metadata: {
      ApiType: 'Azure'
      Type: 'bing_grounding'
      ResourceId: bingGroundingServiceId
      Location: 'global'
    }
  }
}

// Outputs
output bingGroundingConnectionName string = bingGroundingConnection.name
output bingGroundingConnectionId string = bingGroundingConnection.id
output endpoint string = 'https://api.bing.microsoft.com/'
