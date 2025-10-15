param appName string
param location string = resourceGroup().location
param tags object = {}
param serviceName string

@description('The environment variables for the container in key value pairs')
param env object = {}

@secure()
@description('Secrets from Key Vault that need to be resolved')
param keyVaultSecrets object = {}

param identityId string
param containerRegistryName string
param containerAppsEnvironmentId string // New parameter to accept environment ID
param exists bool
param targetPort int = 80

module fetchLatestImage './fetch-container-image.bicep' = {
  name: '${appName}-fetch-image'
  params: {
    exists: exists
  }
}

// Build environment variables array
var regularEnvVars = [
  for key in objectKeys(env): {
    name: key
    value: '${env[key]}'
  }
]

var secretEnvVars = [
  for secretKey in objectKeys(keyVaultSecrets): {
    name: secretKey
    secretRef: toLower(replace(secretKey, '_', '-'))
  }
]

var allEnvVars = concat(regularEnvVars, secretEnvVars)

// Removed containerAppsEnvironment resource as we'll use existing one

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: union(tags, {'azd-service-name': serviceName})
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId // Use the provided environment ID
    workloadProfileName: 'Consumption'
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
      secrets: [
        for secretKey in objectKeys(keyVaultSecrets): {
          name: toLower(replace(secretKey, '_', '-'))
          keyVaultUrl: keyVaultSecrets[secretKey]
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          image: fetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'main'
          env: allEnvVars
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
