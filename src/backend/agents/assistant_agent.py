"""Assistant agent definition responsible for administrative tasks such as email."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
    start_time = time.perf_counter()
    
    recipient = params.get("to", "unknown")
    subject = params.get("subject", "")
    body_preview = params.get("body", "")[:100]  # First 100 chars for logging
    
    logger.info(
        f"[Assistant_Agent][Email] Starting email send request\n"
        f"  To: {recipient}\n"
        f"  Subject: {subject}\n"
        f"  Body preview: {body_preview}{'...' if len(params.get('body', '')) > 100 else ''}"
    )
    
    if not SEND_EMAIL_LOGIC_APP_URL:
        logger.warning("[Assistant_Agent][Email] SEND_EMAIL_LOGIC_APP_URL is not configured")
        return "Email service is not configured."

    try:
        logger.debug(f"[Assistant_Agent][Email] Sending POST request to Logic App")
        api_start = time.perf_counter()
        
        response = requests.post(SEND_EMAIL_LOGIC_APP_URL, json=params, timeout=15)
        
        api_elapsed = time.perf_counter() - api_start
        logger.debug(f"[Assistant_Agent][Email] Logic App responded in {api_elapsed:.2f}s with status {response.status_code}")
        
        response.raise_for_status()
        
        total_elapsed = time.perf_counter() - start_time
        logger.info(
            f"[Assistant_Agent][Email] Email sent successfully in {total_elapsed:.2f}s\n"
            f"  To: {recipient}\n"
            f"  Subject: {subject}"
        )
        return "Email sent successfully."
        
    except requests.Timeout as exc:
        elapsed = time.perf_counter() - start_time
        logger.error(
            f"[Assistant_Agent][Email] Request timed out after {elapsed:.2f}s\n"
            f"  To: {recipient}\n"
            f"  Error: {exc}"
        )
        return "Failed to send email: Request timed out."
        
    except requests.HTTPError as exc:
        elapsed = time.perf_counter() - start_time
        logger.error(
            f"[Assistant_Agent][Email] HTTP error after {elapsed:.2f}s\n"
            f"  To: {recipient}\n"
            f"  Status: {response.status_code}\n"
            f"  Error: {exc}"
        )
        return f"Failed to send email: HTTP {response.status_code}"
        
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - start_time
        logger.exception(
            f"[Assistant_Agent][Email] Failed to send email after {elapsed:.2f}s\n"
            f"  To: {recipient}\n"
            f"  Error: {exc}"
        )
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
