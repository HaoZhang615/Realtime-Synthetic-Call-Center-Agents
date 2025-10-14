// ============================================================================
// AI Foundry MCP Server Container App Module
// ============================================================================
// Deploys the AI Foundry MCP Server as an Azure Container App with:
// - Internal ingress only (not exposed to internet)
// - Managed identity for Azure AI Foundry access
// - Health probes for startup and liveness
// - Environment variables for AI Foundry configuration
// ============================================================================

@description('Container App name')
param appName string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Tags to apply to resources')
param tags object = {}

@description('Managed identity ID for Azure authentication')
param identityId string

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('Container registry name')
param containerRegistryName string

@description('Whether the app already exists (for updates)')
param exists bool = false

@description('Service name for image tagging')
param serviceName string = 'ai-foundry-mcp'

@description('Container port')
param targetPort int = 8000

@description('Environment variables for the container')
param env object = {}

@description('Key Vault secrets to inject as environment variables')
@secure()
param keyVaultSecrets object = {}

// ============================================================================
// Resources
// ============================================================================

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = {
  name: containerRegistryName
}

// Convert env and keyVaultSecrets to arrays for container environment
var envVars = [
  for envVar in items(env): {
    name: envVar.key
    value: envVar.value
  }
]

var secretRefs = [
  for secret in items(keyVaultSecrets): {
    name: secret.key
    secretRef: toLower(secret.key)
  }
]

// AI Foundry MCP Server Container App
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: union(tags, { 'azd-service-name': serviceName })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false  // Internal only - not exposed to internet
        targetPort: targetPort
        transport: 'http'
        allowInsecure: false  // Enforce HTTPS for internal traffic
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: identityId
        }
      ]
      secrets: [
        for secret in items(keyVaultSecrets): {
          name: toLower(secret.key)
          keyVaultUrl: secret.value
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          image: exists 
            ? '${containerRegistry.properties.loginServer}/${serviceName}:${take(uniqueString(resourceGroup().id), 8)}'
            : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'  // Placeholder for initial deployment
          name: serviceName
          env: union(envVars, secretRefs)
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              failureThreshold: 30  // 5 minutes total (10s * 30)
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 0
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Container App resource ID')
output id string = app.id

@description('Container App name')
output name string = app.name

@description('Container App FQDN (internal)')
output fqdn string = 'https://${app.properties.configuration.ingress.fqdn}'

@description('Container App service name for azd')
output serviceName string = serviceName
