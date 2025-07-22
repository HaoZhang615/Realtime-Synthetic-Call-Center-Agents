param envName string
param location string = resourceGroup().location
param tags object = {}


param logAnalyticsWorkspaceName string
@description('Subnet resource ID for VNet integration (optional)')
param appSubnetId string = ''

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = { name: logAnalyticsWorkspaceName }

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
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
    vnetConfiguration: !empty(appSubnetId) ? {
      infrastructureSubnetId: appSubnetId
    } : null
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

output name string = containerAppsEnvironment.name
output id string = containerAppsEnvironment.id
output defaultDomain string = containerAppsEnvironment.properties.defaultDomain
