// Grounding with Bing Custom Search Service
// This module deploys a Bing Custom Search service specifically designed for AI grounding scenarios
// It provides controlled search results from specified domains for more accurate AI responses

param bingSearchServiceName string
param location string = 'global'
param tags object = {}

@description('SKU for the Bing Custom Search service')
@allowed(['F1', 'S1', 'S2', 'S3', 'G2'])
param skuName string = 'G2'

@description('Allowed domains for custom search')
param allowedDomains array = []

@description('Blocked domains for custom search')
param blockedDomains array = []

// Bing Custom Search Service for Grounding
// Reference: https://github.com/microsoft/semantic-kernel/blob/main/python/samples/concepts/agents/azure_ai_agent/azure_ai_agent_bing_grounding.py
resource bingSearchService 'Microsoft.Bing/accounts@2025-05-01-preview' = {
  name: bingSearchServiceName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  kind: 'Bing.GroundingCustomSearch'
}

// Custom Search Configuration
resource bingCustomSearchConfiguration 'Microsoft.Bing/accounts/customSearchConfigurations@2025-05-01-preview' = if (!empty(allowedDomains)) {
  parent: bingSearchService
  name: 'defaultConfiguration'
  properties: {
    allowedDomains: [for domain in allowedDomains: {
      domain: domain
      includeSubPages: false
    }]
    blockedDomains: [for domain in blockedDomains: {
      domain: domain
    }]
  }
}

// Outputs
output bingSearchServiceId string = bingSearchService.id
output bingSearchServiceName string = bingSearchService.name
output bingCustomSearchConfigurationId string = !empty(allowedDomains) ? bingCustomSearchConfiguration.id : ''
output endpoint string = 'https://api.bing.microsoft.com/v7.0/custom/search'
output customConfigId string = !empty(allowedDomains) ? bingCustomSearchConfiguration.name : ''
