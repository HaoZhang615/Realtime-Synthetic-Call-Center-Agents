// Grounding with Bing Custom Search Service
// This module deploys a Bing Custom Search service specifically designed for AI grounding scenarios
// It provides controlled search results from specified domains for more accurate AI responses

param bingCustomSearchServiceName string
param location string = 'global'
param tags object = {}

// Bing Custom Search Service for Grounding
// Reference: https://github.com/microsoft/semantic-kernel/blob/main/python/samples/concepts/agents/azure_ai_agent/azure_ai_agent_bing_grounding.py
resource bingSearchService 'Microsoft.Bing/accounts@2025-05-01-preview' = {
  name: bingCustomSearchServiceName
  location: location
  tags: tags
  sku: {
    name: 'G2'
  }
  kind: 'Bing.GroundingCustomSearch'
}

// Custom Search Configuration
resource bingCustomSearchConfiguration 'Microsoft.Bing/accounts/customSearchConfigurations@2025-05-01-preview' = {
  parent: bingSearchService
  name: 'defaultConfiguration'
  properties: {
    allowedDomains: [
      {
        domain: 'https://www.mobiliar.ch/ratgeber/'
        includeSubPages: false
      }
    ]
    blockedDomains: []
  }
}

// Outputs
output bingCustomSearchServiceId string = bingSearchService.id
output bingCustomSearchServiceName string = bingSearchService.name
output bingCustomSearchConfigurationId string = bingCustomSearchConfiguration.id
output endpoint string = 'https://api.bing.microsoft.com/v7.0/custom/search'
output customConfigId string = bingCustomSearchConfiguration.name
@secure()
output apiKey string = bingSearchService.listKeys().key1
