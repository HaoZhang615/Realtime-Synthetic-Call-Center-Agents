# Multi-Agent Tool Execution Flow (After Fixes)

## Scenario: User on database_agent asks "What products are available?"

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│   Browser   │         │   FastAPI    │         │  Azure OpenAI   │
│   (React)   │         │   Backend    │         │   Realtime API  │
└─────────────┘         └──────────────┘         └─────────────────┘
      │                        │                          │
      │  1. Audio stream       │                          │
      ├───────────────────────>│                          │
      │                        │  2. Append audio buffer  │
      │                        ├─────────────────────────>│
      │                        │                          │
      │                        │  3. response.created     │
      │                        │<─────────────────────────┤
      │                        │                          │
      │                        │  4. function_call_args   │
      │                        │     .done (get_products) │
      │                        │<─────────────────────────┤
      │                        │                          │
      │                        │ ┌──────────────────────┐ │
      │                        │ │ _handle_tool_call    │ │
      │                        │ │ - Log session/agent  │ │
      │                        │ │ - Execute tool       │ │
      │                        │ │ - Get product list   │ │
      │                        │ └──────────────────────┘ │
      │                        │                          │
      │                        │  5. conversation.item.   │
      │                        │     create (output)      │
      │                        ├─────────────────────────>│
      │                        │                          │
      │                        │  6. session.update ⭐NEW │
      │                        │     (refresh db_agent    │
      │                        │      instructions+tools) │
      │                        ├─────────────────────────>│
      │                        │                          │
      │                        │  7. response.create      │
      │                        ├─────────────────────────>│
      │                        │                          │
      │                        │  8. response.audio.delta │
      │  9. Play audio         │<─────────────────────────┤
      │<───────────────────────┤                          │
      │                        │                          │
```

## Key Changes (⭐)

### Step 6: Dynamic Session Refresh (NEW!)
**Before**: Skipped this step - Azure lost agent context  
**After**: Always send fresh session config after tool execution

```python
# Backend now sends:
{
  "type": "session.update",
  "session": {
    "instructions": "You are database_agent...",  # Current agent
    "tools": [...database_tools, ...other_agents_as_tools],
    "voice": "shimmer",  # User's preference preserved
    "modalities": ["text", "audio"]
  }
}
```

### Logging at Each Step
```
[Session:xyz][Customer:alice][Agent:database_agent] Processing tool call: get_products
[Session:xyz][Agent:database_agent] Tool get_products arguments: {}
[Session:xyz][Agent:database_agent] Refreshed session context after tool execution
[Session:xyz][Agent:database_agent] Tool get_products completed in 0.45s
```

---

## Agent Switch Scenario

When user says "Actually, search the web for latest news"

```
      │                        │  function_call_args.done │
      │                        │  (assistant_web_search)  │
      │                        │<─────────────────────────┤
      │                        │                          │
      │                        │ ┌──────────────────────┐ │
      │                        │ │ Agent switch logic:  │ │
      │                        │ │ - Detect "assistant_"│ │
      │                        │ │ - Update active_agents│ │
      │                        │ │ - Merge session state│ │
      │                        │ └──────────────────────┘ │
      │                        │                          │
      │                        │  session.update          │
      │                        │  (web_search_agent       │
      │                        │   instructions+tools)    │
      │                        ├─────────────────────────>│
      │                        │                          │
      │                        │  response.create         │
      │                        ├─────────────────────────>│
```

Logs show transition:
```
[Session:xyz][Customer:alice] Agent switched from database_agent to assistant_web_search
[Session:xyz][Agent:assistant_web_search] Refreshed session context after tool execution
```

---

## Session State Composition

Every `session.update` now merges three layers:

```python
Layer 1: Default config          Layer 2: Previous session     Layer 3: New overrides
├─ voice: "shimmer"              ├─ voice: "alloy" (user)     ├─ instructions: "..."
├─ modalities: [text, audio]     ├─ turn_detection: {...}     ├─ tools: [...]
├─ input_audio_format: pcm16     └─ ...                       └─ ...
└─ ...
                    ↓
            Composed session sent to Azure
            (User preferences + Agent config)
```

This ensures:
✅ Voice selection persists across agent switches  
✅ Turn detection settings preserved  
✅ Agent instructions always current  
✅ Tool list stays accurate
