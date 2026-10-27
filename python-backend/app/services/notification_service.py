"""
Notification configuration and delivery for tenants.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.core.security import decrypt_value, encrypt_value
from app.domain.models.notifications import NotificationConfiguration
from app.infrastructure.push import PushDeliveryError, send_firebase_push, send_twilio_notify_push
from app.infrastructure.sms import SmsDeliveryError, send_twilio_sms
from app.schemas.notification_schemas import (
    NotificationConfigDto,
    TestPushRequest,
    TestSmsRequest,
    UpdateNotificationConfigInput,
)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_or_create_config(self, tenant_id: Optional[uuid.UUID]) -> NotificationConfiguration:
        obj = (
            await self._db.execute(
                select(NotificationConfiguration).where(
                    NotificationConfiguration.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if obj is None:
            obj = NotificationConfiguration(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                created_at=datetime.now(timezone.utc),
            )
            self._db.add(obj)
            await self._db.commit()
            await self._db.refresh(obj)
        return obj

    def to_dto(self, obj: NotificationConfiguration) -> NotificationConfigDto:
        return NotificationConfigDto(
            id=obj.id,
            tenant_id=obj.tenant_id,
            sms_enabled=obj.sms_enabled,
            twilio_account_sid=obj.twilio_account_sid,
            twilio_from_number=obj.twilio_from_number,
            has_twilio_auth_token=bool(obj.twilio_auth_token_encrypted),
            push_enabled=obj.push_enabled,
            push_provider=obj.push_provider,  # type: ignore[arg-type]
            firebase_project_id=obj.firebase_project_id,
            has_firebase_credentials=bool(obj.firebase_credentials_encrypted),
            twilio_notify_service_sid=obj.twilio_notify_service_sid,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    async def update_config(
        self,
        tenant_id: Optional[uuid.UUID],
        inp: UpdateNotificationConfigInput,
    ) -> NotificationConfiguration:
        obj = await self.get_or_create_config(tenant_id)

        if inp.sms_enabled is not None:
            obj.sms_enabled = inp.sms_enabled
        if inp.twilio_account_sid is not None:
            obj.twilio_account_sid = inp.twilio_account_sid.strip() or None
        if inp.twilio_auth_token:
            obj.twilio_auth_token_encrypted = encrypt_value(inp.twilio_auth_token)
        if inp.twilio_from_number is not None:
            obj.twilio_from_number = inp.twilio_from_number.strip() or None

        if inp.push_enabled is not None:
            obj.push_enabled = inp.push_enabled
        if inp.push_provider is not None:
            if inp.push_provider not in ("firebase", "twilio"):
                raise BusinessException("VALIDATION_ERROR", "push_provider must be 'firebase' or 'twilio'")
            obj.push_provider = inp.push_provider
        if inp.firebase_project_id is not None:
            obj.firebase_project_id = inp.firebase_project_id.strip() or None
        if inp.firebase_credentials_json:
            obj.firebase_credentials_encrypted = encrypt_value(inp.firebase_credentials_json.strip())
        if inp.twilio_notify_service_sid is not None:
            obj.twilio_notify_service_sid = inp.twilio_notify_service_sid.strip() or None

        if obj.sms_enabled and not (obj.twilio_account_sid and obj.twilio_auth_token_encrypted and obj.twilio_from_number):
            raise BusinessException(
                "VALIDATION_ERROR",
                "SMS requires Twilio Account SID, Auth Token, and From Number.",
            )
        if obj.push_enabled:
            if not obj.push_provider:
                raise BusinessException("VALIDATION_ERROR", "Select a push provider (firebase or twilio).")
            if obj.push_provider == "firebase":
                if not (obj.firebase_project_id and obj.firebase_credentials_encrypted):
                    raise BusinessException(
                        "VALIDATION_ERROR",
                        "Firebase push requires Project ID and Service Account JSON.",
                    )
            elif obj.push_provider == "twilio":
                if not (obj.twilio_account_sid and obj.twilio_auth_token_encrypted and obj.twilio_notify_service_sid):
                    raise BusinessException(
                        "VALIDATION_ERROR",
                        "Twilio push requires Account SID, Auth Token, and Notify Service SID.",
                    )

        obj.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        await self._db.refresh(obj)
        return obj

    def _twilio_credentials(self, obj: NotificationConfiguration) -> tuple[str, str]:
        if not obj.twilio_account_sid or not obj.twilio_auth_token_encrypted:
            raise BusinessException("VALIDATION_ERROR", "Twilio is not configured for this tenant.")
        return obj.twilio_account_sid, decrypt_value(obj.twilio_auth_token_encrypted)

    async def send_test_sms(self, tenant_id: Optional[uuid.UUID], req: TestSmsRequest) -> dict:
        obj = await self.get_or_create_config(tenant_id)
        if not obj.sms_enabled:
            raise BusinessException("VALIDATION_ERROR", "SMS is disabled. Enable it in notification settings.")
        account_sid, auth_token = self._twilio_credentials(obj)
        try:
            sid = send_twilio_sms(
                account_sid=account_sid,
                auth_token=auth_token,
                from_number=obj.twilio_from_number or "",
                to=req.to,
                body=req.message,
            )
            return {"success": True, "message_sid": sid}
        except SmsDeliveryError as e:
            raise BusinessException("DELIVERY_FAILED", str(e)) from e

    async def send_test_push(self, tenant_id: Optional[uuid.UUID], req: TestPushRequest) -> dict:
        obj = await self.get_or_create_config(tenant_id)
        if not obj.push_enabled or not obj.push_provider:
            raise BusinessException("VALIDATION_ERROR", "Push notifications are disabled.")

        tenant_key = str(tenant_id or "host")

        try:
            if obj.push_provider == "firebase":
                if not req.device_token:
                    raise BusinessException("VALIDATION_ERROR", "device_token is required for Firebase test push.")
                creds = decrypt_value(obj.firebase_credentials_encrypted or "")
                msg_id = send_firebase_push(
                    tenant_key=tenant_key,
                    credentials_json=creds,
                    device_token=req.device_token,
                    title=req.title,
                    body=req.body,
                )
                return {"success": True, "message_id": msg_id, "provider": "firebase"}

            account_sid, auth_token = self._twilio_credentials(obj)
            sid = send_twilio_notify_push(
                account_sid=account_sid,
                auth_token=auth_token,
                notify_service_sid=obj.twilio_notify_service_sid or "",
                title=req.title,
                body=req.body,
                identity=req.identity,
                binding_address=req.binding_address,
                binding_type=req.binding_type,
            )
            return {"success": True, "notification_sid": sid, "provider": "twilio"}
        except PushDeliveryError as e:
            raise BusinessException("DELIVERY_FAILED", str(e)) from e
