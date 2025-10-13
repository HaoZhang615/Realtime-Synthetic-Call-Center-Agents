// Azure AI Services Account (AI Foundry) module
// Based on: https://github.com/azure-ai-foundry/foundry-samples/tree/main/samples/microsoft/infrastructure-setup/45-basic-agent-bing
// Extended to support multiple model deployments

@description('Name of the AI Services account')
param accountName string

@description('Location for the AI Services account')
param location string

@description('Tags to apply to the resource')
param tags object = {}

@description('Array of model deployments')
param deployments array = []

@description('Key Vault resource ID for storing keys')
param keyVaultResourceId string = ''

@description('User-assigned identity principal ID for RBAC')
param appIdentityPrincipalId string = ''

@description('Principal ID for owner/admin RBAC')
param principalId string = ''

@description('Principal type for owner/admin RBAC')
param principalType string = 'User'

// Create AI Services Account (AI Foundry resource)
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  tags: tags
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Required for AI Foundry project management
    allowProjectManagement: true
    
    // Custom subdomain for API endpoint
    customSubDomainName: accountName
    
    // Network configuration
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    
    // Disable key-based auth (use Entra ID)
    disableLocalAuth: false
  }
}

// Deploy models
@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for deployment in deployments: {
  parent: account
  name: deployment.name
  sku: deployment.sku
  properties: {
    model: deployment.model
    versionUpgradeOption: deployment.?versionUpgradeOption ?? 'OnceNewDefaultVersionAvailable'
  }
}]

// Store keys in Key Vault if provided
resource keyVaultSecretKey1 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(keyVaultResourceId)) {
  name: '${split(keyVaultResourceId, '/')[8]}/${accountName}-accessKey1'
  properties: {
    value: account.listKeys().key1
  }
}

resource keyVaultSecretKey2 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(keyVaultResourceId)) {
  name: '${split(keyVaultResourceId, '/')[8]}/${accountName}-accessKey2'
  properties: {
    value: account.listKeys().key2
  }
}

// RBAC assignments
resource cognitiveServicesUserRoleApp 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appIdentityPrincipalId)) {
  name: guid(account.id, appIdentityPrincipalId, 'CognitiveServicesUser')
  scope: account
  properties: {
    principalId: appIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalType: 'ServicePrincipal'
  }
}

resource cognitiveServicesUserRolePrincipal 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(account.id, principalId, 'CognitiveServicesUser')
  scope: account
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalType: principalType
  }
}

resource cognitiveServicesOpenAIUserRoleApp 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appIdentityPrincipalId)) {
  name: guid(account.id, appIdentityPrincipalId, 'CognitiveServicesOpenAIUser')
  scope: account
  properties: {
    principalId: appIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: 'ServicePrincipal'
  }
}

resource cognitiveServicesOpenAIUserRolePrincipal 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(account.id, principalId, 'CognitiveServicesOpenAIUser')
  scope: account
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: principalType
  }
}

// Outputs
output accountName string = account.name
output accountId string = account.id
output accountEndpoint string = account.properties.endpoint
output accountPrincipalId string = account.identity.principalId
output resourceId string = account.id
output name string = account.name
output endpoint string = account.properties.endpoint
