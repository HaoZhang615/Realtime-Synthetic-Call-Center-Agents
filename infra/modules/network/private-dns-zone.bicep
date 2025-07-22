param privateEndpointId string
param privateDnsZoneName string
param vnetId string
param tags object = {}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneName
  location: 'global'
  tags: tags
}

resource privateDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: '${privateDnsZoneName}-vnet-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// Need to reference the private endpoint by its full resource path
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-02-01' existing = {
  name: last(split(privateEndpointId, '/'))
}

resource privateDnsZoneGroupAttachment 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-02-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: privateDnsZoneName
        properties: {
          privateDnsZoneId: privateDnsZone.id
        }
      }
    ]
  }
}

output privateDnsZoneId string = privateDnsZone.id
