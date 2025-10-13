// AI Foundry Project RBAC module
// Assigns Azure AI Developer role to principals

@description('Principal ID to grant access')
param principalId string

@description('Principal type (User, ServicePrincipal, Group)')
param principalType string = 'ServicePrincipal'

@description('AI Foundry Project resource ID')
param projectResourceId string

// Azure AI Developer role definition
// https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#azure-ai-developer
var aiDeveloperRoleId = '64702f94-c441-49e6-a78b-ef80e0188fee'

// Extract project name from resource ID for unique GUID generation
var projectNameFromId = last(split(projectResourceId, '/'))

// Assign Azure AI Developer role
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(principalId, aiDeveloperRoleId, projectNameFromId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', aiDeveloperRoleId)
    principalId: principalId
    principalType: principalType
  }
}

output roleAssignmentId string = roleAssignment.id
