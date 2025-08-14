"""Module to retrieve geographical location from WhatsApp using Twilio integration. Handles environment variable checks and errors gracefully."""

import os
import logging
from typing import Optional
from .whats_app_location import WhatsAppLocationClient

logger = logging.getLogger(__name__)

def get_geo_location() -> Optional[str]:
    """
    Retrieve geographical location from WhatsApp using Twilio.
    Returns location as a string, or None if not available.
    """
    target = os.getenv("TWILIO_WHATSAPP_TO")
    if not target:
        logger.error("Environment variable TWILIO_WHATSAPP_TO is not set.")
        return None
    try:
        client = WhatsAppLocationClient()
        result = client.get_location_via_whatsapp(target, timeout_seconds=60, poll_interval_seconds=5)
        return str(result)
    except Exception as e:
        logger.error(f"Failed to get location via WhatsApp: {e}")
        return None

