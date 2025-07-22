param name string
param location string = resourceGroup().location
param subnetId string
param groupId string
param privateLinkResourceId string
param tags object = {}

resource pe 'Microsoft.Network/privateEndpoints@2023-02-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${name}-pls'
        properties: {
          privateLinkServiceId: privateLinkResourceId
          groupIds: [groupId]
        }
      }
    ]
  }
}

output id string = pe.id
