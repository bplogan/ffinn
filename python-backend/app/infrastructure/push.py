"""
Push notification delivery — Firebase Cloud Messaging or Twilio Notify.
"""
from __future__ import annotations

import json
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


class PushDeliveryError(Exception):
    pass


def _firebase_app_name(tenant_key: str) -> str:
    return f"ffinn-fcm-{tenant_key}"


def send_firebase_push(
    *,
    tenant_key: str,
    credentials_json: str,
    device_token: str,
    title: str,
    body: str,
) -> str:
    """Send a push notification via Firebase Cloud Messaging."""
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError as e:
        raise PushDeliveryError("firebase-admin package is not installed") from e

    app_name = _firebase_app_name(tenant_key)
    try:
        cred = credentials.Certificate(json.loads(credentials_json))
    except json.JSONDecodeError as e:
        raise PushDeliveryError("Firebase credentials must be valid JSON") from e

    try:
        firebase_admin.get_app(app_name)
    except ValueError:
        firebase_admin.initialize_app(cred, name=app_name)

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=device_token.strip(),
    )
    try:
        msg_id = messaging.send(message, app=firebase_admin.get_app(app_name))
        log.info("Firebase push sent", message_id=msg_id)
        return msg_id
    except Exception as e:
        log.warning("Firebase push failed", error=str(e))
        raise PushDeliveryError(str(e)) from e


def send_twilio_notify_push(
    *,
    account_sid: str,
    auth_token: str,
    notify_service_sid: str,
    title: str,
    body: str,
    identity: Optional[str] = None,
    binding_address: Optional[str] = None,
    binding_type: Optional[str] = None,
) -> str:
    """Send a push notification via Twilio Notify."""
    try:
        from twilio.rest import Client
    except ImportError as e:
        raise PushDeliveryError("twilio package is not installed") from e

    if not notify_service_sid:
        raise PushDeliveryError("Twilio Notify Service SID is required")

    client = Client(account_sid, auth_token)
    payload = {"title": title, "body": body}
    kwargs: dict = {"body": json.dumps(payload)}

    if identity:
        kwargs["identity"] = identity.strip()
    elif binding_address and binding_type:
        kwargs["to_binding"] = json.dumps({"binding_type": binding_type, "address": binding_address})
    else:
        raise PushDeliveryError(
            "Provide identity (Twilio Notify user) or binding_address + binding_type for a test push"
        )

    try:
        notification = client.notify.services(notify_service_sid).notifications.create(**kwargs)
        log.info("Twilio Notify push sent", sid=notification.sid)
        return notification.sid
    except Exception as e:
        log.warning("Twilio Notify push failed", error=str(e))
        raise PushDeliveryError(str(e)) from e
