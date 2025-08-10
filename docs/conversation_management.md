# Conversation Management System

## Overview

The conversation management system integrates Cosmos DB with the VoiceBot Classic application to persistently store and retrieve conversation history. This allows users to maintain conversation context across sessions and provides conversation analytics.

## Document Schema

The `AI_Conversations` container stores conversation documents with the following simplified schema:

```json
{
  "id": "unique_conversation_id",
  "customer_id": "session_or_user_identifier", 
  "session_id": "streamlit_session_id",
  "created_at": "2025-01-24T10:30:00Z",
  "updated_at": "2025-01-24T10:35:00Z", 
  "messages": [
    {
      "role": "user",
      "content": "user message content",
      "timestamp": "2025-01-24T10:30:00Z"
    },
    {
      "role": "assistant", 
      "content": "assistant response",
      "timestamp": "2025-01-24T10:30:15Z"
    }
  ]
}
```

## Key Features

### 🔐 Security
- Uses Azure Managed Identity for authentication
- No hardcoded credentials
- Implements proper error handling and retry logic

### 📊 Conversation Tracking
- Automatic conversation creation for each session
- Real-time message saving after each interaction
- Simple message storage with role, content, and timestamp

### 🔄 Session Management
- Unique session IDs for each Streamlit session
- Customer ID generation for conversation partitioning
- Support for loading previous conversations

### 🎛️ User Controls
- Start new conversation button
- Recent conversations viewer

## Implementation Files

### `utils/conversation_manager.py`
Core conversation management class with methods for:
- Creating conversation documents
- Adding messages to conversations
- Saving/loading from Cosmos DB
- Retrieving recent conversations
- Deleting conversations

### Updated `04_VoiceBot_Classic.py`
Enhanced with:
- Conversation manager integration
- Session management functions
- Automatic conversation saving
- Sidebar conversation controls

### `test_conversation_manager.py`
Test script to verify Cosmos DB integration and basic functionality.

## Environment Variables Required

```bash
COSMOSDB_ENDPOINT=<your_cosmos_endpoint>
COSMOSDB_DATABASE=<your_database_name>
COSMOSDB_AIConversations_CONTAINER=<container_name>
```

## Usage

### Basic Integration
The conversation manager is automatically initialized when the VoiceBot Classic page loads:

```python
from utils.conversation_manager import ConversationManager

# Initialize
conversation_manager = ConversationManager()

# Create conversation
conversation_doc = conversation_manager.create_conversation_document(
    customer_id="user_123",
    session_id="session_456"
)

# Add messages
conversation_manager.add_message_to_conversation(
    conversation_doc,
    role="user",
    content="Hello"
)

# Save to Cosmos DB
conversation_manager.save_conversation(conversation_doc)
```

### Testing
Run the test script to verify functionality:

```bash
cd src/backend
python test_conversation_manager.py
```

## Cosmos DB Configuration

The system uses the existing Cosmos DB configuration from the infrastructure:
- **Container**: `AI_Conversations`
- **Partition Key**: `/customer_id`
- **Database**: `GenAI` (configurable via environment)

## Error Handling

The system implements comprehensive error handling:
- Graceful degradation when Cosmos DB is unavailable
- Retry logic for transient failures
- Detailed logging for troubleshooting
- Non-blocking errors that don't interrupt user experience

## Future Enhancements

- **Conversation Analytics**: Track conversation metrics and user satisfaction
- **Search**: Full-text search across conversation history
- **Export**: Export conversations to different formats
- **Multi-user**: Support for authenticated users with proper customer IDs
- **Conversation Sharing**: Share conversations between users
- **Archive**: Automatic archiving of old conversations
