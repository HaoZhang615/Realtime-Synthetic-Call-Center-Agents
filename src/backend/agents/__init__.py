"""Agent definitions for the backend multi-agent orchestration layer."""

from __future__ import annotations

import sys
import os

# Add the backend directory to path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from load_azd_env import load_azd_environment
    # Ensure Azure Developer CLI environment variables are available when agents are imported.
    load_azd_environment()
except ImportError as e:
    import logging
    logging.warning(f"Could not load azd environment: {e}")
