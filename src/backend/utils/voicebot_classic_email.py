"""
Email service operations for VoiceBot Classic.
Contains functions for sending emails via Azure Logic App.
"""

import os
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

def send_email(params: Dict[str, Any]) -> str:
    """
    Send an email using Azure Logic App.
    
    Args:
        params (dict): Email parameters including:
            - to: Recipient email address
            - subject: Email subject
            - body: Email body content
    
    Returns:
        str: Success or error message
    """
    try:
        send_email_logic_app_url = os.getenv("SEND_EMAIL_LOGIC_APP_URL")
        
        if not send_email_logic_app_url:
            logger.error("SEND_EMAIL_LOGIC_APP_URL environment variable not set")
            return "Email service is not configured. Please contact administrator."
        
        logger.info(f"Sending email to: {params.get('to', 'unknown')}")
        logger.debug(f"Email subject: {params.get('subject', 'No subject')}")
        
        response = requests.post(send_email_logic_app_url, json=params)
        response.raise_for_status()
        
        logger.info("Email sent successfully")
        return "Email sent successfully."
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error sending email: {e}")
        return f"Failed to send email due to network error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return f"Failed to send email: {e}"
