// Azure AI Foundry - Bing Search Connection module
// Based on: https://github.com/azure-ai-foundry/foundry-samples/tree/main/samples/microsoft/infrastructure-setup/45-basic-agent-bing

@description('Name of the AI Services account')
param accountName string

@description('Name of the Bing Search resource')
param bingSearchName string

@description('Name of the AI Foundry project')
param projectName string

// Reference to existing AI Services account
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

// Reference to existing Bing Search resource
#disable-next-line BCP081
resource bingSearch 'Microsoft.Bing/accounts@2020-06-10' existing = {
  name: bingSearchName
}

// Create connection from AI Foundry account to Bing Search
resource bingConnection 'Microsoft.CognitiveServices/accounts/connections@2025-07-01-preview' = {
  name: replace(bingSearchName, '-', '')
  parent: account
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    isSharedToAll: false
    credentials: {
      #disable-next-line prefer-unquoted-property-names
      key: bingSearch.listKeys('2020-06-10').key1
    }
    metadata: {
      ApiType: 'Azure'
      Type: 'GroundingWithBingSearch'
      Location: bingSearch.location
      ResourceId: bingSearch.id
    }
  }
}

// Outputs
output connectionName string = bingConnection.name
output connectionId string = '${account.id}/projects/${projectName}/connections/${bingConnection.name}'
