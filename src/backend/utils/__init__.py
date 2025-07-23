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