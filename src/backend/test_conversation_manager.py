#!/usr/bin/env python3
"""
Test script for ConversationManager to verify Cosmos DB integration.
Run this script to test conversation saving and retrieval functionality.
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils import load_dotenv_from_azd
from utils.conversation_manager import ConversationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_conversation_manager():
    """Test basic functionality of ConversationManager."""
    
    print("🧪 Testing ConversationManager...")
    
    # Load environment variables
    print("📝 Loading environment variables...")
    load_dotenv_from_azd()
    
    # Initialize conversation manager
    print("🔌 Initializing ConversationManager...")
    try:
        conv_manager = ConversationManager()
        print("✅ ConversationManager initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize ConversationManager: {e}")
        return False
    
    # Test conversation creation
    print("📄 Creating test conversation...")
    test_customer_id = "test_customer_123"
    test_session_id = "test_session_456"
    
    conversation_doc = conv_manager.create_conversation_document(
        customer_id=test_customer_id,
        session_id=test_session_id
    )
    
    print(f"📋 Created conversation: {conversation_doc['id']}")
    
    # Add test messages
    print("💬 Adding test messages...")
    conv_manager.add_message_to_conversation(
        conversation_doc,
        role="user",
        content="Hello, this is a test message"
    )
    
    conv_manager.add_message_to_conversation(
        conversation_doc,
        role="assistant", 
        content="Hello! I'm responding to your test message."
    )
    
    print(f"📊 Conversation now has {len(conversation_doc['messages'])} messages")
    
    # Test saving to Cosmos DB
    print("💾 Saving conversation to Cosmos DB...")
    success = conv_manager.save_conversation(conversation_doc)
    
    if success:
        print("✅ Conversation saved successfully")
    else:
        print("❌ Failed to save conversation")
        return False
    
    # Test retrieval
    print("📖 Testing conversation retrieval...")
    retrieved_doc = conv_manager.get_conversation(
        conversation_doc['id'], 
        test_customer_id
    )
    
    if retrieved_doc:
        print("✅ Conversation retrieved successfully")
        print(f"📝 Retrieved {len(retrieved_doc['messages'])} messages")
    else:
        print("❌ Failed to retrieve conversation")
        return False
    
    # Test recent conversations
    print("📚 Testing recent conversations retrieval...")
    recent_convs = conv_manager.get_recent_conversations(test_customer_id, limit=5)
    print(f"📋 Found {len(recent_convs)} recent conversations")
    
    # Cleanup - delete test conversation
    print("🧹 Cleaning up test data...")
    deleted = conv_manager.delete_conversation(conversation_doc['id'], test_customer_id)
    
    if deleted:
        print("✅ Test conversation deleted successfully")
    else:
        print("⚠️ Warning: Failed to delete test conversation")
    
    print("🎉 All tests completed successfully!")
    return True

if __name__ == "__main__":
    try:
        success = test_conversation_manager()
        if success:
            print("\n✨ ConversationManager is working correctly!")
            sys.exit(0)
        else:
            print("\n💥 ConversationManager tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        sys.exit(1)
