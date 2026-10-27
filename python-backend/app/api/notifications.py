"""
Tenant notification configuration — Twilio SMS and push (Firebase or Twilio Notify).

Routes:
  GET  /api/notifications/config      - get current tenant config
  PUT  /api/notifications/config      - create/update config
  POST /api/notifications/test-sms    - send test SMS
  POST /api/notifications/test-push   - send test push
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.exceptions import ForbiddenException
from app.schemas.notification_schemas import (
    NotificationConfigDto,
    TestPushRequest,
    TestSmsRequest,
    UpdateNotificationConfigInput,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _require_notifications_admin(user: CurrentUser) -> None:
    if not user.is_admin() and not user.has_permission("Settings.Notifications"):
        raise ForbiddenException("Admin or Settings.Notifications permission required.")


@router.get("/config", response_model=NotificationConfigDto)
async def get_notification_config(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_notifications_admin(current_user)
    svc = NotificationService(db)
    obj = await svc.get_or_create_config(current_user.tenant_id)
    return svc.to_dto(obj)


@router.put("/config", response_model=NotificationConfigDto)
async def update_notification_config(
    body: UpdateNotificationConfigInput,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_notifications_admin(current_user)
    svc = NotificationService(db)
    obj = await svc.update_config(current_user.tenant_id, body)
    return svc.to_dto(obj)


@router.post("/test-sms")
async def test_sms(
    body: TestSmsRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_notifications_admin(current_user)
    svc = NotificationService(db)
    return await svc.send_test_sms(current_user.tenant_id, body)


@router.post("/test-push")
async def test_push(
    body: TestPushRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_notifications_admin(current_user)
    svc = NotificationService(db)
    return await svc.send_test_push(current_user.tenant_id, body)
