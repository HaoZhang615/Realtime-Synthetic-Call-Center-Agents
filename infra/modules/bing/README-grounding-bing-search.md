# Grounding with Bing Search Service

This module deploys a Bing Grounding service for AI grounding scenarios. It provides general web search capabilities for AI applications.

## Overview

This module creates only the Bing Grounding resource (`Microsoft.Bing/accounts` with kind `Bing.Grounding`). It is designed to be used in conjunction with the AI Foundry connection module to establish the complete grounding solution.

## Resources Created

- **Microsoft.Bing/accounts** (kind: 'Bing.Grounding'): The Bing Grounding service

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bingGroundingServiceName` | string | | Name of the Bing Grounding service |
| `location` | string | 'global' | Location for the service (must be 'global' for Bing services) |
| `tags` | object | {} | Tags to be applied to resources |
| `skuName` | string | 'G1' | SKU for the service (G1, G2) |
| `statisticsEnabled` | bool | false | Whether to enable statistics for the service |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `bingGroundingServiceId` | string | Resource ID of the Bing Grounding service |
| `bingGroundingServiceName` | string | Name of the Bing Grounding service |
| `endpoint` | string | API endpoint for Bing search |

## Usage Example

```bicep
module bingGroundingService 'modules/bing/grounding-bing-search.bicep' = {
  name: 'bingGroundingService'
  params: {
    bingGroundingServiceName: 'my-bing-grounding-service'
    skuName: 'G1'
    statisticsEnabled: false
  }
}
```

## Idempotent Deployments

Bicep deployments are naturally idempotent. Running the same deployment multiple times will not create duplicate resources - Azure Resource Manager will recognize that the resource already exists and skip creation.

This module focuses solely on resource creation and does not include complex conditional logic for existing resources, making it simpler and more predictable.

## Key Differences from Custom Search

This module creates a **Bing Grounding** service, which is different from **Bing Custom Search**:

- **Bing Grounding**: General web search service for AI grounding
- **Bing Custom Search**: Domain-specific search with custom configurations

## Complete Solution

To create a complete AI grounding solution, use this module together with the AI Foundry connection module:

1. **This module** (`modules/bing/grounding-bing-search.bicep`): Creates the Bing Grounding service
2. **Connection module** (`modules/aifoundry/connection-bing-grounding.bicep`): Creates the AI Foundry connection

## References

- [Bing Grounding Documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/bing-web-search/)
- [Azure AI Foundry Grounding](https://docs.microsoft.com/en-us/azure/ai-studio/concepts/grounding)
