"""
Standalone WhatsApp helper using Twilio:
- Sends a message asking the user to share their location.
- Waits up to `timeout_seconds` for a reply.
- Tries to extract GPS coordinates from the reply text (maps links or "lat,lon").
- Returns a dict with either {'coordinates': (lat, lon), 'raw': reply_text}
  or {'coordinates': None, 'raw': reply_text or None} if nothing found.

IMPORTANT:
- This polling approach CANNOT see Twilio’s webhook-only fields (Latitude/Longitude).
- For guaranteed coordinates, implement an inbound webhook (Twilio sends Latitude/Longitude there).
"""

import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from twilio.rest import Client
import requests

load_dotenv()

PROMPT_TEXT = "Bitte auf die Briefklammer unten rechts im Eingabefeld drücken und den Standort senden."
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")


def _parse_coords_from_text(text: str) -> Optional[Tuple[float, float]]:
    """
    Best-effort coordinate extraction from plain text:
    - Match decimal pairs like '47.3769, 8.5417'
    - Extract from common Google Maps URLs (…/place/47.3769,8.5417 or ?q=47.3769,8.5417)
    Returns (lat, lon) or None.
    """
    if not text:
        return None

    # 1) Generic "lat,lon" (supports +/- and spaces)
    m = re.search(r"([-+]?\d{1,2}\.\d+)\s*,\s*([-+]?\d{1,3}\.\d+)", text)
    if m:
        try:
            lat = float(m.group(1))
            lon = float(m.group(2))
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return (lat, lon)
        except ValueError:
            pass

    # 2) Google Maps query param q=lat,lon or @lat,lon zoom forms
    #    Examples:
    #      https://maps.google.com/?q=47.3769,8.5417
    #      https://www.google.com/maps/@47.3769,8.5417,14z
    m = re.search(r"[?&]q=([-+]?\d{1,2}\.\d+),([-+]?\d{1,3}\.\d+)", text)
    if m:
        try:
            lat = float(m.group(1)); lon = float(m.group(2))
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return (lat, lon)
        except ValueError:
            pass

    m = re.search(r"/@([-+]?\d{1,2}\.\d+),([-+]?\d{1,3}\.\d+),", text)
    if m:
        try:
            lat = float(m.group(1)); lon = float(m.group(2))
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return (lat, lon)
        except ValueError:
            pass

    return None

def _parse_coords_from_function_payload(payload: dict):
    """Extract coordinates from Twilio Function JSON.""" 
    lat = payload.get("Latitude") or payload.get("latitude")
    lon = payload.get("Longitude") or payload.get("longitude")
    if lat and lon:
        try:
            return float(lat), float(lon)
        except ValueError:
            pass
    return None

class WhatsAppLocationClient:
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_whatsapp: Optional[str] = None,
        *,
        function_url: Optional[str] = None,
        prompt_text: str = PROMPT_TEXT,
    ) -> None:
        load_dotenv()

        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = from_whatsapp or os.getenv("TWILIO_WHATSAPP_FROM")
        self.function_url = function_url or os.getenv("TWILIO_FUNCTION_URL")
        self.prompt_text = prompt_text

        if not all([self.account_sid, self.auth_token, self.from_whatsapp]):
            raise RuntimeError(
                "Missing TWILIO_* environment variables. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM."
            )

        self.client = Client(self.account_sid, self.auth_token)

    def get_location_via_whatsapp(
        self,
        phone_number: str,
        *,
        timeout_seconds: int = 60,
        poll_interval_seconds: int = 5,
    ) -> Dict[str, object]:
        """
        Send a WhatsApp message asking the user to share location and wait for a reply.

        Returns:
            {
              'coordinates': (lat, lon) or None,
              'raw': reply payload or None,
              'message_sid': outbound_sid,
              'received_at': ISO8601 or None
            }
        """
        # 1) Send prompt
        msg = self.client.messages.create(
            from_=self.from_whatsapp,
            to=phone_number,
            body=self.prompt_text,
        )
        send_time = datetime.now(timezone.utc)

        # 2) Poll for inbound reply via Twilio Function aggregator
        deadline = time.time() + timeout_seconds
        last_seen = None

        while time.time() < deadline:
            try:
                resp = requests.get(
                    self.function_url,
                    params={
                        "user": phone_number,
                        "since": send_time.isoformat(),
                        "consume": "1",
                    },
                    timeout=5,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data and data != last_seen:
                        last_seen = data
                        coords = _parse_coords_from_function_payload(data)
                        # Optional fallback: try to parse coords from any text payload
                        if not coords:
                            if isinstance(data, dict):
                                text = data.get("Body") or data.get("body") or ""
                            else:
                                text = str(data)
                            coords = _parse_coords_from_text(text)

                        return {
                            "coordinates": coords,
                            "raw": data,
                            "message_sid": msg.sid,
                            "received_at": datetime.now(timezone.utc).isoformat(),
                        }
                elif resp.status_code == 204:
                    pass
                else:
                    pass
            except Exception as e:
                print("Error polling function:", e)
            time.sleep(poll_interval_seconds)

        return {
            "coordinates": None,
            "raw": None,
            "message_sid": msg.sid,
            "received_at": None,
        }

if __name__ == "__main__":
    # Example call:
    # IMPORTANT: Use the 'whatsapp:' prefix and your actual number.
    target = os.getenv("TWILIO_WHATSAPP_TO")
    client = WhatsAppLocationClient()
    result = client.get_location_via_whatsapp(target, timeout_seconds=60, poll_interval_seconds=5)
    print('result from Whatsapp:', result)


