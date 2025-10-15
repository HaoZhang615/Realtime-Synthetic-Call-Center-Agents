// Grounding with Bing Search Service
// This module deploys a Bing Grounding service for AI grounding scenarios
// It provides general web search capabilities for AI applications

param bingGroundingServiceName string
param tags object = {}

@description('SKU for the Bing Grounding service')
@allowed(['G1', 'G2'])
param skuName string = 'G1'

@description('Whether to enable statistics for the Bing Grounding service')
param statisticsEnabled bool = false

// Creates a new Bing Grounding resource
resource bingGroundingService 'Microsoft.Bing/accounts@2020-06-10' = {
  name: bingGroundingServiceName
  location: 'global'
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    statisticsEnabled: statisticsEnabled
  }
  kind: 'Bing.Grounding'
}

// Outputs
output bingGroundingServiceId string = bingGroundingService.id
output bingGroundingServiceName string = bingGroundingService.name
output bingGroundingServiceLocation string = bingGroundingService.location
output endpoint string = 'https://api.bing.microsoft.com/'
@secure()
output apiKey string = bingGroundingService.listKeys().key1

