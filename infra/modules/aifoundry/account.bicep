targetScope = 'resourceGroup'

@description('Name of the AI Foundry account')
param name string

@description('Location for the AI Foundry account')
param location string

@description('Model deployments for the AI Foundry account')
param deployments array

@description('Tags to apply to the resource')
param tags object = {}

@description('Principal ID of the user or service principal')
param principalId string

@description('Principal type (User or ServicePrincipal)')
param principalType string

@description('Principal ID of the app identity')
param appIdentityPrincipalId string

@description('Name of the Key Vault to store secrets')
param keyVaultName string

resource aiFoundryAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

// Deploy models to the AI Foundry account
@batchSize(1)
resource aiFoundryDeployments 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for deployment in deployments: {
  parent: aiFoundryAccount
  name: deployment.name
  sku: deployment.sku
  properties: {
    model: deployment.model
  }
}]

// Role assignments for app identity
resource appIdentityRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, appIdentityPrincipalId, 'Cognitive Services OpenAI User')
  scope: aiFoundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') // Cognitive Services OpenAI User
    principalId: appIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Role assignments for user/service principal
resource userRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, principalId, 'Cognitive Services OpenAI User')
  scope: aiFoundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') // Cognitive Services OpenAI User
    principalId: principalId
    principalType: principalType
  }
}

// Reference to existing Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Store AI Foundry keys in Key Vault
resource aiFoundryKey1Secret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: '${name}-accessKey1'
  properties: {
    value: aiFoundryAccount.listKeys().key1
  }
}

resource aiFoundryKey2Secret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: '${name}-accessKey2'
  properties: {
    value: aiFoundryAccount.listKeys().key2
  }
}

output endpoint string = aiFoundryAccount.properties.endpoint
output name string = aiFoundryAccount.name
output id string = aiFoundryAccount.id
