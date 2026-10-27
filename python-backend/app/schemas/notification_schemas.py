"""Notification configuration DTOs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class NotificationConfigDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: uuid.UUID
    tenant_id: Optional[uuid.UUID] = None
    sms_enabled: bool = False
    twilio_account_sid: Optional[str] = None
    twilio_from_number: Optional[str] = None
    has_twilio_auth_token: bool = False
    push_enabled: bool = False
    push_provider: Optional[Literal["firebase", "twilio"]] = None
    firebase_project_id: Optional[str] = None
    has_firebase_credentials: bool = False
    twilio_notify_service_sid: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateNotificationConfigInput(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    sms_enabled: Optional[bool] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None  # omit to keep existing
    twilio_from_number: Optional[str] = None
    push_enabled: Optional[bool] = None
    push_provider: Optional[Literal["firebase", "twilio"]] = None
    firebase_project_id: Optional[str] = None
    firebase_credentials_json: Optional[str] = None  # omit to keep existing
    twilio_notify_service_sid: Optional[str] = None


class TestSmsRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    to: str = Field(..., min_length=8, description="E.164 phone number, e.g. +15551234567")
    message: str = Field(default="Test SMS from ffinn", max_length=1600)


class TestPushRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str = Field(default="ffinn test", max_length=200)
    body: str = Field(default="Push notifications are working.", max_length=1000)
    # Firebase: FCM device token
    device_token: Optional[str] = None
    # Twilio Notify: user identity or binding JSON
    identity: Optional[str] = None
    binding_address: Optional[str] = None
    binding_type: Optional[str] = None  # e.g. fcm, apn
