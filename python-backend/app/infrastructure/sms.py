"""
SMS delivery via Twilio.
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


class SmsDeliveryError(Exception):
    pass


def send_twilio_sms(
    *,
    account_sid: str,
    auth_token: str,
    from_number: str,
    to: str,
    body: str,
) -> str:
    """Send an SMS via Twilio. Returns the message SID."""
    try:
        from twilio.rest import Client
    except ImportError as e:
        raise SmsDeliveryError("twilio package is not installed") from e

    if not account_sid or not auth_token:
        raise SmsDeliveryError("Twilio account SID and auth token are required")
    if not from_number:
        raise SmsDeliveryError("Twilio from number is required")

    client = Client(account_sid, auth_token)
    try:
        msg = client.messages.create(to=to.strip(), from_=from_number.strip(), body=body)
        log.info("Twilio SMS sent", sid=msg.sid, to=to)
        return msg.sid
    except Exception as e:
        log.warning("Twilio SMS failed", error=str(e), to=to)
        raise SmsDeliveryError(str(e)) from e
