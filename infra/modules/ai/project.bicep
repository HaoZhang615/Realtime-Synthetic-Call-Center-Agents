// Azure AI Foundry Project module
// Based on: https://github.com/azure-ai-foundry/foundry-samples/tree/main/samples/microsoft/infrastructure-setup/45-basic-agent-bing

@description('Name of the parent AI Services account')
param accountName string

@description('Name of the AI Foundry project')
param projectName string

@description('Location for the project')
param location string

@description('Project description')
param projectDescription string = 'AI Foundry project for realtime call center agents'

@description('Project display name')
param projectDisplayName string

@description('Tags to apply to the resource')
param tags object = {}

// Reference to existing AI Services account
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

// Create AI Foundry Project as sub-resource of the account
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDescription
    displayName: projectDisplayName
  }
}

// Outputs
output projectName string = project.name
output projectId string = project.id
output projectPrincipalId string = project.identity.principalId
