param cosmosDbAccountName string 
param databaseName string = 'GenAI'
param location string = resourceGroup().location
param tags object = {}

param identityName string
resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = { name: identityName }

param principalId string
param principalType string

// Create Cosmos DB account
resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosDbAccountName
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags  // Added tags usage
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

// Create a database within the Cosmos DB account
resource cosmosDbDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  name: databaseName
  parent: cosmosDbAccount
  properties: {
    resource: {
      id: databaseName
    }
    options: {}
  }
}

resource AIConversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: 'AI_Conversations'
  location: location
  parent: cosmosDbDatabase
  properties: {
    resource: {
      id: 'AI_Conversations'
      createMode: 'Default'
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/customer_id'
        ]
      }
    }
    options: {
    }
  }
}
resource CustomerContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: 'Customer'
  location: location
  parent: cosmosDbDatabase
  properties: {
    resource: {
      id: 'Customer'
      createMode: 'Default'
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/customer_id'
        ]
      }
    }
    options: {
    }
  }
}
resource HumanConversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: 'Human_Conversations'
  location: location
  parent: cosmosDbDatabase
  properties: {
    resource: {
      id: 'Human_Conversations'
      createMode: 'Default'
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/customer_id'
        ]
      }
    }
    options: {
    }
  }
}
resource ProductContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: 'Product'
  location: location
  parent: cosmosDbDatabase
  properties: {
    resource: {
      id: 'Product'
      createMode: 'Default'
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/product_id'
        ]
      }
    }
    options: {
    }
  }
}
resource PurchasesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: 'Purchases'
  location: location
  parent: cosmosDbDatabase
  properties: {
    resource: {
      id: 'Purchases'
      createMode: 'Default'
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/customer_id'
        ]
      }
    }
    options: {
    }
  }
}

resource ProductUrlContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: 'ProductUrl'
  location: location
  parent: cosmosDbDatabase
  properties: {
    resource: {
      id: 'ProductUrl'
      createMode: 'Default'
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/company_name'
        ]
      }
    }
    options: {
    }
  }
}

/*
  SEE
    https://github.com/Azure/azure-quickstart-templates/blob/master/quickstarts/microsoft.kusto/kusto-cosmos-db/main.bicep
    https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac#permission-model
*/


// Assign the User Assigned Identity Contributor role to the Cosmos DB account
resource cosmosDbAccountRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(cosmosDbAccount.id, appIdentity.id, 'cosmosDbContributor')
  scope: cosmosDbAccount
  properties: {
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') // Role definition ID for Contributor
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource cosmosDbAccountRoleAssignmentPrincipal 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(cosmosDbAccount.id, principalId, 'cosmosDbContributor')
  scope: cosmosDbAccount
  properties: {
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') // Role definition ID for Contributor
    principalId: principalId
    principalType: principalType
  }
}

var cosmosDataContributor = '00000000-0000-0000-0000-000000000002'

resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2021-04-15' = {
  name: guid(cosmosDataContributor, appIdentity.id, cosmosDbAccount.id)
  parent: cosmosDbAccount
  properties: {
    roleDefinitionId: resourceId('Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions', cosmosDbAccountName, cosmosDataContributor)
    principalId: appIdentity.properties.principalId
    scope: cosmosDbAccount.id
  }
}

resource sqlRoleAssignmentPrincipal 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2021-04-15' = {
  name: guid(cosmosDataContributor, principalId, cosmosDbAccount.id)
  parent: cosmosDbAccount
  properties: {
    roleDefinitionId: resourceId('Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions', cosmosDbAccountName, cosmosDataContributor)
    principalId: principalId
    scope: cosmosDbAccount.id
  }
}

output cosmosDbDatabase string = cosmosDbDatabase.name
output cosmosDbAIConversationsContainer string = AIConversationsContainer.name
output cosmosDbCustomerContainer string = CustomerContainer.name
output cosmosDbHumanConversationsContainer string = HumanConversationsContainer.name
output cosmosDbProductContainer string = ProductContainer.name
output cosmosDbPurchasesContainer string = PurchasesContainer.name
output cosmosDbProductUrlContainer string = ProductUrlContainer.name
output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
