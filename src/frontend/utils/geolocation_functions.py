"""Module to retrieve geographical location from WhatsApp using Twilio integration. Handles environment variable checks and errors gracefully."""

import os
import logging
from typing import Optional
from .whats_app_location import WhatsAppLocationClient

logger = logging.getLogger(__name__)

def get_geo_location() -> str:
    """
    Retrieve geographical location from WhatsApp using Twilio.
    Returns location as a string, or error message if not available.
    """
    target = os.getenv("TWILIO_WHATSAPP_TO")
    if not target:
        logger.error("Environment variable TWILIO_WHATSAPP_TO is not set.")
        return "Error: WhatsApp target not configured."
    try:
        client = WhatsAppLocationClient()
        result = client.get_location_via_whatsapp(target, timeout_seconds=60, poll_interval_seconds=5)
        return str(result)  # Always return a string, even if result is None
    except Exception as e:
        logger.error(f"Failed to get location via WhatsApp: {e}")
        return f"Error: Failed to get location via WhatsApp: {str(e)}"
