# Grounding with Bing Custom Search Configuration Examples

## Example 1: Microsoft Documentation Sites

```json
{
  "allowedDomains": [
    "docs.microsoft.com",
    "learn.microsoft.com",
    "azure.microsoft.com",
    "github.com/microsoft"
  ],
  "blockedDomains": [
    "social.msdn.microsoft.com"
  ]
}
```

## Example 2: E-commerce Sites (for product search)

```json
{
  "allowedDomains": [
    "amazon.com",
    "ebay.com",
    "shopify.com",
    "etsy.com"
  ],
  "blockedDomains": [
    "fake-store.com",
    "suspicious-deals.net"
  ]
}
```

## Example 3: News and Research Sites

```json
{
  "allowedDomains": [
    "reuters.com",
    "bbc.com",
    "nature.com",
    "sciencedirect.com",
    "arxiv.org"
  ],
  "blockedDomains": [
    "fake-news-site.com",
    "conspiracy-theories.net"
  ]
}
```

## Usage in Bicep Parameters

To use these configurations, update your `main.parameters.json`:

```json
{
  "bingSearchAllowedDomains": {
    "value": [
      "docs.microsoft.com",
      "learn.microsoft.com",
      "azure.microsoft.com"
    ]
  },
  "bingSearchBlockedDomains": {
    "value": [
      "suspicious-site.com"
    ]
  }
}
```

## Usage in Environment Variables

You can also set these via environment variables:

```bash
# For Azure Developer CLI (azd)
azd env set BING_SEARCH_ALLOWED_DOMAINS '["docs.microsoft.com","learn.microsoft.com"]'
azd env set BING_SEARCH_BLOCKED_DOMAINS '["spam-site.com"]'
```
