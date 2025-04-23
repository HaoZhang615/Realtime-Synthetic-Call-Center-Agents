param appName string
param location string = resourceGroup().location
param tags object = {}
param serviceName string

@description('The environment variables for the container in key value pairs')
param env object = {}

param identityId string
param containerRegistryName string
param logAnalyticsWorkspaceName string
param containerAppsEnvironmentId string // New parameter to accept environment ID
param exists bool
param targetPort int = 80

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = { name: logAnalyticsWorkspaceName }

module fetchLatestImage './fetch-container-image.bicep' = {
  name: '${appName}-fetch-image'
  params: {
    exists: exists
  }
}

// Removed containerAppsEnvironment resource as we'll use existing one

resource app 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: appName
  location: location
  tags: union(tags, {'azd-service-name': serviceName})
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId // Use the provided environment ID
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistryName}.azurecr.io'
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          image: fetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'main'
          env: [
            for key in objectKeys(env): {
              name: key
              value: '${env[key]}'
            }
          ]
          resources: {
            cpu: json('1.0')
            memory: '2.0Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

// Removed defaultDomain output as it's not available anymore
output name string = app.name
output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
output id string = app.id
