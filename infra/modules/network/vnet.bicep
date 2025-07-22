param vnetName string
param location string = resourceGroup().location
param addressPrefix string = '10.0.0.0/16'
param backendSubnetPrefix string = '10.0.1.0/24'
param appSubnetPrefix string = '10.0.0.0/27'
param tags object = {}

resource vnet 'Microsoft.Network/virtualNetworks@2023-02-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [addressPrefix]
    }
    subnets: [
      {
        name: 'backend'
        properties: {
          addressPrefix: backendSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'apps'
        properties: {
          addressPrefix: appSubnetPrefix
          delegations: [
            {
              name: 'containerapps'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output backendSubnetId string = vnet.properties.subnets[0].id
output appSubnetId string = vnet.properties.subnets[1].id
