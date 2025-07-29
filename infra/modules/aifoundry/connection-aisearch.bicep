@description('AI Foundry account name')
param aiFoundryAccountName string

@description('Azure AI Search service name')
param searchServiceName string

@description('Azure AI Search service location')
param searchServiceLocation string

@description('Azure AI Search service resource ID')
param searchServiceResourceId string

@description('AI Foundry project managed identity principal ID')
param projectPrincipalId string

// Reference to the existing AI Foundry account
resource aiFoundryAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiFoundryAccountName
}

// Reference to the existing Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2025-02-01-preview' existing = {
  name: searchServiceName
}

// Assign required roles to the AI Foundry project managed identity for Azure AD authentication
// As per Microsoft documentation: "If you use Microsoft Entra ID for the connection authentication type, 
// you need to manually assign the project managed identity the roles Search Index Data Contributor 
// and Search Service Contributor to the Azure AI Search resource."
resource searchIndexDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, projectPrincipalId, 'Search Index Data Contributor')
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7') // Search Index Data Contributor
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource searchServiceContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, projectPrincipalId, 'Search Service Contributor')
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0') // Search Service Contributor
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Creates the AI Foundry connection to Azure AI Search service
// Connection name must match the AI Search service name per Microsoft documentation
resource aiSearchConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: searchServiceName
  parent: aiFoundryAccount
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${searchServiceName}.search.windows.net'
    authType: 'AAD' // Using Azure AD authentication for better security
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchServiceResourceId
      location: searchServiceLocation
    }
  }
  dependsOn: [
    searchIndexDataContributorRole
    searchServiceContributorRole
  ]
}

output connectionName string = aiSearchConnection.name
output connectionId string = aiSearchConnection.id
