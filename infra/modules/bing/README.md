# Grounding with Bing Custom Search Module

This module deploys a "Grounding With Bing Custom Search" resource using Azure Bicep.

## Overview

The Bing Custom Search service allows you to create a tailored search experience for specific domains or websites. This is particularly useful for AI grounding scenarios where you want to limit search results to trusted sources.

## Resources Created

- **Microsoft.Bing/accounts**: The main Bing Custom Search service
- **Microsoft.Bing/accounts/customSearchConfigurations**: Custom search configuration with allowed and blocked domains

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bingSearchServiceName` | string | | Name of the Bing Custom Search service |
| `location` | string | 'global' | Location for the service (must be 'global' for Bing services) |
| `tags` | object | {} | Tags to be applied to resources |
| `skuName` | string | 'G2' | SKU for the service (F1, S1, S2, S3, G2) |
| `allowedDomains` | array | [] | List of domains to include in custom search |
| `blockedDomains` | array | [] | List of domains to exclude from custom search |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `bingSearchServiceId` | string | Resource ID of the Bing Search service |
| `bingSearchServiceName` | string | Name of the Bing Search service |
| `bingCustomSearchConfigurationId` | string | Resource ID of the custom search configuration |
| `endpoint` | string | API endpoint for custom search |
| `customConfigId` | string | Custom configuration ID for API calls |

## Usage Example

```bicep
module bingCustomSearch 'modules/bing/grounding-bing-custom-search.bicep' = {
  name: 'bingCustomSearch'
  params: {
    bingSearchServiceName: 'my-custom-search'
    allowedDomains: [
      'docs.microsoft.com'
      'learn.microsoft.com'
      'azure.microsoft.com'
    ]
    blockedDomains: [
      'example.com'
    ]
    skuName: 'G2'
  }
}
```

## Environment Variables

The following environment variables are automatically set for container apps:

- `BING_CUSTOM_SEARCH_SERVICE_NAME`: Name of the Bing Custom Search service
- `BING_CUSTOM_SEARCH_ENDPOINT`: API endpoint for custom search
- `BING_CUSTOM_SEARCH_CONFIG_ID`: Custom configuration ID

## API Usage

To use the custom search in your application:

```python
import requests

endpoint = os.environ.get('BING_CUSTOM_SEARCH_ENDPOINT')
config_id = os.environ.get('BING_CUSTOM_SEARCH_CONFIG_ID')
api_key = os.environ.get('BING_SEARCH_API_KEY')  # From Key Vault

url = f"{endpoint}?q={query}&customconfig={config_id}"
headers = {'Ocp-Apim-Subscription-Key': api_key}

response = requests.get(url, headers=headers)
```

## References

- [Bing Custom Search API Documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/bing-custom-search/)
- [Semantic Kernel Bing Grounding Sample](https://github.com/microsoft/semantic-kernel/blob/main/python/samples/concepts/agents/azure_ai_agent/azure_ai_agent_bing_grounding.py)
