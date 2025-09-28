"""Assistant agent definition responsible for administrative tasks such as email."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

SEND_EMAIL_LOGIC_APP_URL = os.getenv("SEND_EMAIL_LOGIC_APP_URL")


def send_email(params: Dict[str, Any]) -> str:
    """Trigger the Logic App workflow to send an email.

    Parameters
    ----------
    params:
        A dictionary containing ``to``, ``subject`` and ``body`` keys that will
        be forwarded to the Logic App endpoint.

    Returns
    -------
    str
        A short status message describing whether the request succeeded.
    """
    if not SEND_EMAIL_LOGIC_APP_URL:
        logger.warning("SEND_EMAIL_LOGIC_APP_URL is not configured; cannot send email")
        return "Email service is not configured."

    try:
        response = requests.post(SEND_EMAIL_LOGIC_APP_URL, json=params, timeout=15)
        response.raise_for_status()
        return "Email sent successfully."
    except requests.RequestException as exc:
        logger.exception("Failed to send email via Logic App")
        return f"Failed to send email: {exc}"


assistant_agent: Dict[str, Any] = {
    "id": "Assistant_Executive_Assistant",
    "name": "Executive Assistant",
    "description": (
        "Call this agent when you need to send an email or summarise the "
        "conversation for the user."
    ),
    "system_message": (
        "You are an executive assistant that helps with administrative tasks.\n"
        "Interaction goes over voice, so it's super important that answers are "
        "as short as possible. Use professional language.\n\n"
        "Your tasks are, upon the user's request:\n"
        "- Provide a structured summary of the conversation.\n"
        "- Send an email using the send_email tool after confirming details.\n"
    ),
    "tools": [
        {
            "name": "send_email",
            "description": "Send an email to the specified user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": (
                            "The recipient's email address."
                        ),
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject line of the email.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The body content of the email.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
            "returns": send_email,
        }
    ],
}
