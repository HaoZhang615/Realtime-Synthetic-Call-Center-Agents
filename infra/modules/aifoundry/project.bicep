targetScope = 'resourceGroup'

@description('Name of the AI Foundry account')
param aiFoundryAccountName string

@description('Name of the AI Foundry project')
param projectName string

@description('Location for the AI Foundry project')
param location string

resource aiFoundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  name: '${aiFoundryAccountName}/${projectName}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {

  }
}

output projectName string = aiFoundryProject.name
output projectId string = aiFoundryProject.id
output projectPrincipalId string = aiFoundryProject.identity.principalId
output projectEndpoint string = aiFoundryProject.properties.endpoints['AI Foundry API']
