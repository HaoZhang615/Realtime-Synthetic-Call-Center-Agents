"""Utility module for loading environment variables from AZD or .env files."""

import logging
from io import StringIO
from subprocess import run, PIPE
from dotenv import load_dotenv

def load_dotenv_from_azd():
    """Load environment variables from AZD environment or fallback to .env file."""
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True, check=False)
    if result.returncode == 0:
        logging.info("Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info("AZD environment not found. Trying to load from .env file...")
        load_dotenv()

# Make conversation manager available
try:
    from .conversation_manager import ConversationManager
    __all__ = ['load_dotenv_from_azd', 'ConversationManager']
except ImportError:
    # Conversation manager dependencies not available
    __all__ = ['load_dotenv_from_azd']

# Make common utilities available
try:
    from .voicebot_common import *
    from .agent_common import *
    from .streamlit_ui_common import *
    
    # Update __all__ to include common utilities
    __all__.extend([
        # VoiceBot common functions
        'setup_logging_and_monitoring', 'initialize_azure_clients', 'get_session_id',
        'get_customer_id', 'get_current_datetime', 'initialize_conversation', 'save_conversation_to_cosmos',
        'speech_to_text', 'text_to_speech', 'save_conversation_message',
        'setup_sidebar_voice_controls', 'setup_sidebar_conversation_info',
        'display_conversation_history', 'process_audio_and_text_input',
        'cleanup_response_for_tts', 
        
        # Agent common functions
        'find_existing_agent_by_name', 'find_existing_agent_by_name_async',
        'initialize_ai_project_client', 'get_environment_variables',
        'get_agent_instructions', 'cleanup_agent_resources',
        'validate_agent_configuration', 'log_agent_creation',
        
        # Streamlit UI common functions
        'setup_page_header', 'setup_sidebar_header', 'setup_voice_input_recorder',
        'setup_system_message_input', 'setup_voice_instruction_examples',
        'create_chat_container', 'process_user_input', 'handle_audio_recording',
        'display_chat_message', 'show_processing_spinner', 'setup_sidebar_status_section',
        'add_sidebar_separator', 'setup_conversation_reset_button',
        'initialize_session_messages', 'add_message_to_session', 'display_all_messages',
        'handle_chat_flow'
    ])
    
except ImportError as e:
    # Common utilities dependencies not available
    logging.warning(f"Some common utilities not available: {e}")
    pass