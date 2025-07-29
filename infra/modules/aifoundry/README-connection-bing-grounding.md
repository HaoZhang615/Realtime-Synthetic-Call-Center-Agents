# Grounding with Bing Search Connection for AI Foundry

This module creates a connection between an existing Bing Grounding resource and the AI Foundry Project, enabling AI grounding capabilities with Bing Search.

## Overview

This module handles only the AI Foundry connection logic. It assumes that a Bing Grounding resource already exists and creates a connection to it. This follows the separation of concerns principle where resource creation and connection creation are handled separately.

## Resources Created

- **Microsoft.CognitiveServices/accounts/connections**: The AI Foundry connection to the Bing service

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `aiFoundryName` | string | | Name of the existing AI Foundry account |
| `bingGroundingServiceId` | string | | Resource ID of the existing Bing Grounding service |
| `apiKey` | string | | Bing Search API key (secure parameter) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `bingGroundingConnectionName` | string | Name of the AI Foundry connection |
| `bingGroundingConnectionId` | string | Resource ID of the AI Foundry connection |
| `endpoint` | string | API endpoint for Bing search |

## Usage Example

```bicep
module bingGroundingConnection 'modules/aifoundry/connection-bing-grounding.bicep' = {
  name: 'bingGroundingConnection'
  params: {
    aiFoundryName: 'my-ai-foundry-account'
    bingGroundingServiceId: bingGroundingService.outputs.bingGroundingServiceId
    apiKey: bingSearchApiKey
  }
}
```

## Complete Solution

This module is designed to work with the Bing Grounding service module:

1. **Service module** (`modules/bing/grounding-bing-search.bicep`): Creates the Bing Grounding service
2. **This module** (`modules/aifoundry/connection-bing-grounding.bicep`): Creates the AI Foundry connection

## Environment Variables

The following environment variables are automatically set for container apps:

- `BING_GROUNDING_SERVICE_NAME`: Name of the Bing Grounding service
- `BING_GROUNDING_CONNECTION_NAME`: Name of the AI Foundry connection
- `BING_GROUNDING_ENDPOINT`: API endpoint for Bing search

## Key Differences from Custom Search

This module creates a **Grounding with Bing Search** connection, which is different from the **Grounding with Bing Custom Search**:

- **Bing Grounding**: Uses the general web search with AI Foundry integration
- **Bing Custom Search**: Uses domain-specific search with custom configurations

Both can be used together for different use cases in your AI applications.

## AI Foundry Integration

Once deployed, this connection will be available in your AI Foundry project and can be used by:

- Agents and flows that need web search capabilities
- Applications using the AI Foundry SDK
- Prompt flows requiring external grounding data

## API Usage

In your AI Foundry applications, you can reference this connection by name:

```python
# The connection will be available as 'bing-grounding' in AI Foundry
# Use the AI Foundry SDK to access the connection
from azure.ai.projects import AIProjectClient

project = AIProjectClient.from_connection_string(connection_string)
# The Bing grounding connection is now available for use in agents and flows
```

## References

- [Azure AI Foundry Connections Documentation](https://docs.microsoft.com/en-us/azure/ai-studio/how-to/connections-add)
- [Bing Grounding in AI Foundry](https://docs.microsoft.com/en-us/azure/ai-studio/concepts/grounding)
- [Foundry Samples Repository](https://github.com/azure-ai-foundry/foundry-samples)
