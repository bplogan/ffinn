"""
User delegation routes.

Endpoints:
  GET    /api/delegations/my-delegations    — delegations I created
  GET    /api/delegations/delegations-to-me — delegations assigned to me
  GET    /api/delegations/all               — all delegations (admin)
  GET    /api/delegations/{id}              — get by ID
  POST   /api/delegations                  — create delegation
  PUT    /api/delegations/{id}             — update delegation
  DELETE /api/delegations/{id}             — delete delegation
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.dependencies import DBSession, get_current_user, CurrentUser, AdminUser
from app.services.identity_services import DelegationService

router = APIRouter(prefix="/api/delegations", tags=["Delegations"])


# ── Request Models ────────────────────────────────────────────────────────────

class CreateDelegationRequest(BaseModel):
    target_user_id: uuid.UUID
    start_time: datetime
    end_time: datetime


class UpdateDelegationRequest(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# ── Helper ────────────────────────────────────────────────────────────────────

def _dto(d) -> dict:
    return {
        "id": str(d.id),
        "tenant_id": str(d.tenant_id) if d.tenant_id else None,
        "source_user_id": str(d.source_user_id),
        "target_user_id": str(d.target_user_id),
        "start_time": d.start_time.isoformat(),
        "end_time": d.end_time.isoformat(),
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/my-delegations")
async def my_delegations(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    """Return delegations that the current user created (as source)."""
    svc = DelegationService(db)
    items = await svc.get_my_delegations(current_user.id)
    return {"items": [_dto(d) for d in items]}


@router.get("/delegations-to-me")
async def delegations_to_me(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    """Return delegations assigned to the current user (as target)."""
    svc = DelegationService(db)
    items = await svc.get_delegations_to_me(current_user.id)
    return {"items": [_dto(d) for d in items]}


@router.get("/all")
async def all_delegations(db: DBSession, current_user: AdminUser):
    """Return all delegations (admin only)."""
    svc = DelegationService(db)
    items = await svc.get_all(current_user.tenant_id)
    return {"items": [_dto(d) for d in items]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_delegation(
    body: CreateDelegationRequest,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = DelegationService(db)
    d = await svc.create(
        source_user_id=current_user.id,
        target_user_id=body.target_user_id,
        start_time=body.start_time,
        end_time=body.end_time,
        tenant_id=current_user.tenant_id,
    )
    return _dto(d)


@router.get("/{delegation_id}")
async def get_delegation(
    delegation_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = DelegationService(db)
    d = await svc.get(delegation_id)
    # Users may only view their own delegations (source or target); admins may view any
    if not current_user.is_admin() and d.source_user_id != current_user.id and d.target_user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied.")
    return _dto(d)


@router.put("/{delegation_id}")
async def update_delegation(
    delegation_id: uuid.UUID,
    body: UpdateDelegationRequest,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = DelegationService(db)
    d = await svc.get(delegation_id)
    # Only the delegation creator (source) or an admin may update it
    if not current_user.is_admin() and d.source_user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied.")
    d = await svc.update(delegation_id, start_time=body.start_time, end_time=body.end_time)
    return _dto(d)


@router.delete("/{delegation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_delegation(
    delegation_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = DelegationService(db)
    d = await svc.get(delegation_id)
    # Only the delegation creator (source) or an admin may delete it
    if not current_user.is_admin() and d.source_user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied.")
    await svc.delete(delegation_id)
