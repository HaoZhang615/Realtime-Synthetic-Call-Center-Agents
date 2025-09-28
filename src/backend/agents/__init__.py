"""Agent definitions for the backend multi-agent orchestration layer."""

from __future__ import annotations

from ..load_azd_env import load_azd_environment

# Ensure Azure Developer CLI environment variables are available when agents are imported.
load_azd_environment()
