param name string
param location string = resourceGroup().location
param tags object = {}

@description('The environment variables for the container in key value pairs')
param env object = {}

param identityId string
// param identityName string
param containerRegistryName string

param logAnalyticsWorkspaceName string
// param applicationInsightsName string

// param azureOpenAIModelEndpoint string
// param azureModelDeploymentName string

// param cosmosDbEndpoint string
// param cosmosDbName string
// param cosmosDbContainer string

param exists bool

// resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31'  existing = { name: identityName }
// resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = { name: applicationInsightsName }
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = { name: logAnalyticsWorkspaceName }

module fetchLatestImage './fetch-container-image.bicep' = {
  name: '${name}-fetch-image'
  params: {
    exists: exists
    name: name
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2022-10-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    // daprAIConnectionString: applicationInsights.properties.ConnectionString
    daprAIConnectionString: env.APPLICATIONINSIGHTS_CONNECTION_STRING
  }
}

resource app 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: name
  location: location
  tags: union(tags, {'azd-service-name':  'app' })
  identity: {
    type: 'UserAssigned'
    // userAssignedIdentities: { '${identity.id}': {} }
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress:  {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistryName}.azurecr.io'
          // identity: identity.id
          identity: identityId
        }
      ]
      // secrets: [
      //   {
      //       name: 'api-key'
      //       value: '${openAIService.listKeys().key1}'
      //   }
      // ]
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
          // env: [
          //   { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
          //   { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsights.properties.ConnectionString }
          //   { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAIModelEndpoint }
          //   { name: 'AZURE_OPENAI_GPT4o_REALTIME_DEPLOYMENT', value: azureModelDeploymentName }
          //   // { name: 'AZURE_OPENAI_API_KEY', value: openAiApiKey }
          //   { name: 'COSMOSDB_ENDPOINT', value: cosmosDbEndpoint }
          //   { name: 'COSMOSDB_DATABASE', value: cosmosDbName }
          //   { name: 'COSMOSDB_CONTAINER', value: cosmosDbContainer }
          // ]
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

output defaultDomain string = containerAppsEnvironment.properties.defaultDomain
output name string = app.name
output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
output id string = app.id
