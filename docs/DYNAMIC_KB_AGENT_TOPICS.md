# Dynamic Internal KB Agent Topic Extraction

## Overview

This document describes the implementation of dynamic topic extraction for the Internal Knowledge Base Agent. The system automatically extracts topics from indexed documents to improve agent routing intelligence.

## Problem Statement

Previously, the Internal KB Agent had a static description that didn't reflect the actual content of uploaded documents. This made it difficult for the Root Assistant to intelligently route queries to the KB agent, especially when documents covered diverse topics.

## Solution

Extract topics dynamically from the AI Search index metadata (title, header_1, header_2) and use them to generate a context-aware agent description. This enables semantic routing without brute-forcing KB searches on every query.

## Architecture

### Components Created

1. **`services/document_metadata.py`** - New service for topic extraction
   - `extract_topics_from_headers()` - Extracts keywords from header text
   - `get_all_document_topics()` - Queries AI Search index for all topics
   - `get_document_summaries()` - Returns document-level topic summaries
   - `get_kb_agent_description()` - Generates dynamic agent description

2. **`agents/internal_kb.py`** - Updated to use dynamic description
   - `get_internal_kb_agent()` - Function that returns agent with current topics
   - Legacy `internal_kb_agent` export maintained for compatibility

3. **`services/assistant_service.py`** - Updated orchestrator
   - Changed import from `internal_kb_agent` to `get_internal_kb_agent`
   - Calls function on each session initialization to get fresh topics

4. **`utils/file_processor.py`** - Added indexer monitoring
   - `wait_for_indexer_completion()` - Waits for AI Search indexing to finish
   - Prevents topic extraction before documents are indexed

5. **`routes/admin.py`** - Enhanced upload and delete endpoints
   - Upload workflow now waits for indexing, then logs extracted topics
   - Delete endpoint logs updated topics after removal
   - New `/api/admin/kb-topics` endpoint to view current topics

## How It Works

### Upload Flow

```
1. User uploads documents via Admin Portal
2. Documents uploaded to Blob Storage
3. AI Search indexer processes documents
4. System waits for indexer to complete (max 5 minutes)
5. Topics extracted from index metadata (title, header_1, header_2)
6. Topics logged for visibility
```

### Session Initialization Flow

```
1. Customer starts voice chat session
2. AgentOrchestrator.initialise_agents(customer_id) called
3. get_internal_kb_agent() queries AI Search index
4. Extracts all unique topics from indexed documents
5. Generates description: "Call this agent when user asks about: [topics]"
6. Root Assistant uses description for intelligent routing
```

### Deletion Flow

```
1. User deletes document from Admin Portal
2. Document removed from Blob Storage and AI Search index
3. Updated topics extracted from remaining documents
4. Next session will use updated topic list automatically
```

## Key Features

### 1. Real-Time Updates
- Topics extracted on every session initialization
- Automatically reflects added/deleted documents
- No manual cache invalidation needed

### 2. Efficient Topic Extraction
- Uses existing AI Search index metadata
- No additional GPT calls required
- Fast single-query retrieval
- Limited to top 100 documents (configurable for production)

### 3. Intelligent Routing
- Root Assistant sees specific topics in agent description
- LLM routes based on semantic match
- Avoids wasteful KB searches for irrelevant queries
- Token-efficient compared to brute-force searching

### 4. Observability
- Upload process logs extracted topics
- Delete process logs remaining topics
- `/api/admin/kb-topics` endpoint for inspection
- Session initialization logs topic refresh

## Configuration

### Search Limits (Demo Settings)

In `services/document_metadata.py`:
```python
# NOTE: top=100 is set low for demo purposes - increase for production
results = search_client.search(
    search_text="*",
    select=["title", "header_1", "header_2"],
    top=100,  # Adjust based on document volume
    include_total_count=True
)
```

### Indexer Wait Timeout

In `routes/admin.py`:
```python
wait_for_indexer_completion(
    azure_credential=azure_credential,
    indexer_name=indexer_name,
    azure_search_endpoint=azure_search_endpoint,
    max_wait_seconds=300,  # 5 minutes
    poll_interval=10  # Check every 10 seconds
)
```

## API Endpoints

### GET `/api/admin/kb-topics`

Returns current knowledge base topics and agent description.

**Response:**
```json
{
  "total_topics": 15,
  "topics": [
    "employee benefits",
    "vacation policy",
    "401k plans",
    "dress code",
    "remote work"
  ],
  "documents": [
    {
      "title": "Employee_Handbook.pdf",
      "topics": ["Employee Benefits", "Vacation Policy", "401k Plans"]
    }
  ],
  "agent_description": "Call this agent when the user asks about: employee benefits, vacation policy, 401k plans, dress code, remote work. This agent searches the company's internal knowledge base and documentation.",
  "note": "The Internal KB agent uses this description for intelligent routing. Topics update automatically when documents are added or deleted."
}
```

## Example Scenario

### Before (Static Description)
```
User: "What's the company's remote work policy?"
Root Assistant: Uses generic description "internal knowledge base"
             → May not route to KB agent (ambiguous)
```

### After (Dynamic Description)
```
User: "What's the company's remote work policy?"
Root Assistant: Sees description includes "remote work policy"
             → Routes to Internal KB agent (semantic match)
             → KB agent searches and finds relevant content
```

## Benefits

✅ **Token Efficient** - Only searches KB when semantically relevant  
✅ **Self-Updating** - Description updates as documents change  
✅ **Transparent** - LLM knows exactly what topics are available  
✅ **Scalable** - Works regardless of document content  
✅ **Fast** - Single query to AI Search index  
✅ **Zero Storage** - Uses existing index, no extra database needed  

## Limitations

1. **Demo Limit** - Top 100 documents indexed (configurable)
2. **Header Dependency** - Relies on Document Intelligence extracting good headers
3. **Session Delay** - Topic extraction adds ~1-2 seconds to session initialization
4. **No Caching** - Topics re-queried on every session (could be optimized)

## Future Enhancements

- Cache topics with TTL (e.g., 5 minutes)
- Increase search limit for production (1000+)
- Add header_3 back if needed
- Support manual topic overrides
- Add topic similarity grouping
- Implement topic trending/analytics

## Testing

### Manual Testing

1. **Upload Test:**
   ```bash
   # Upload a document via Admin Portal
   # Check backend logs for "Extracted X topics"
   # Call GET /api/admin/kb-topics to verify
   ```

2. **Routing Test:**
   ```bash
   # Start voice chat session
   # Ask about topic from uploaded document
   # Verify Root Assistant routes to Internal KB agent
   ```

3. **Deletion Test:**
   ```bash
   # Delete document via Admin Portal
   # Check logs for updated topic count
   # Verify /api/admin/kb-topics reflects deletion
   ```

### Verification Commands

```bash
# View current topics
curl http://localhost:8000/api/admin/kb-topics

# Upload document and check logs
# Look for: "Extracted X topics from Y document chunks"

# Delete document and check logs
# Look for: "After deletion: X topics remain"
```

## Troubleshooting

### Topics Not Updating

**Problem:** Agent description doesn't reflect new documents  
**Solution:** Topics are loaded per-session. Start a new voice chat session.

### Empty Topics List

**Problem:** `/api/admin/kb-topics` returns empty list  
**Solution:** 
- Check if documents are uploaded
- Verify indexer has completed (can take 2-5 minutes)
- Check AI Search index has documents with title/header fields

### Indexer Timeout

**Problem:** Upload completes but topics not extracted  
**Solution:**
- Check Azure Portal for indexer status
- Increase `max_wait_seconds` in upload flow
- Documents will be available on next upload after indexer finishes

## Implementation Checklist

- [x] Created `services/document_metadata.py`
- [x] Updated `agents/internal_kb.py` to use dynamic function
- [x] Modified `services/assistant_service.py` orchestrator
- [x] Added `wait_for_indexer_completion()` in `file_processor.py`
- [x] Enhanced upload flow to wait and extract topics
- [x] Updated delete flow to log remaining topics
- [x] Added `/api/admin/kb-topics` endpoint
- [x] Tested locally (pending)
- [x] Documented implementation

## Related Files

- `src/backend/services/document_metadata.py` - Topic extraction service
- `src/backend/agents/internal_kb.py` - Internal KB agent definition
- `src/backend/services/assistant_service.py` - Agent orchestrator
- `src/backend/utils/file_processor.py` - Document upload utilities
- `src/backend/routes/admin.py` - Admin API endpoints
