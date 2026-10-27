"""
Editions management routes.

Endpoints:
  GET    /api/editions                — list all editions (admin)
  GET    /api/editions/public         — list public editions with features (anonymous)
  GET    /api/editions/for-select     — simplified list for dropdowns
  GET    /api/editions/{id}           — get by ID
  POST   /api/editions                — create
  PUT    /api/editions/{id}           — update
  DELETE /api/editions/{id}           — delete
  GET    /api/editions/{id}/tenant-count  — count tenants on this edition
  POST   /api/editions/move-tenants   — move tenants from one edition to another
  GET    /api/editions/{id}/features  — list features for an edition
  POST   /api/editions/{id}/features  — add a feature to an edition
  PUT    /api/editions/{id}/features/{feature_id}  — update a feature
  DELETE /api/editions/{id}/features/{feature_id}  — delete a feature
  PUT    /api/editions/{id}/features/replace       — replace all features atomically
"""
from __future__ import annotations

import uuid
from typing import Optional, List

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.dependencies import DBSession, AdminUser
from app.services.misc_services import EditionsService

router = APIRouter(prefix="/api/editions", tags=["Editions"])


# ── Request Models ────────────────────────────────────────────────────────────

class CreateEditionRequest(BaseModel):
    display_name: str
    is_free: bool = False
    price_monthly: float = 0
    price_annually: float = 0
    currency: str = "USD"
    sort_order: int = 0
    is_public: bool = True
    trial_day_count: Optional[int] = None
    is_trial_active: bool = False


class UpdateEditionRequest(BaseModel):
    display_name: Optional[str] = None
    is_free: Optional[bool] = None
    price_monthly: Optional[float] = None
    price_annually: Optional[float] = None
    currency: Optional[str] = None
    sort_order: Optional[int] = None
    is_public: Optional[bool] = None
    trial_day_count: Optional[int] = None
    is_trial_active: Optional[bool] = None


class MoveTenantsRequest(BaseModel):
    source_edition_id: uuid.UUID
    target_edition_id: uuid.UUID


class CreateFeatureRequest(BaseModel):
    feature_name: str
    display_name: str
    feature_value: Optional[str] = None
    is_included: bool = True
    sort_order: int = 0


class UpdateFeatureRequest(BaseModel):
    feature_name: Optional[str] = None
    display_name: Optional[str] = None
    feature_value: Optional[str] = None
    is_included: Optional[bool] = None
    sort_order: Optional[int] = None


class ReplaceFeatureItem(BaseModel):
    feature_name: str
    display_name: str
    feature_value: Optional[str] = None
    is_included: bool = True
    sort_order: int = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _feature_dto(f) -> dict:
    return {
        "id": str(f.id),
        "edition_id": str(f.edition_id),
        "feature_name": f.feature_name,
        "display_name": f.display_name,
        "feature_value": f.feature_value,
        "is_included": f.is_included,
        "sort_order": f.sort_order,
    }


def _edition_dto(e, include_features: bool = False) -> dict:
    d = {
        "id": str(e.id),
        "display_name": e.display_name,
        "is_free": e.is_free,
        "price_monthly": float(e.price_monthly),
        "price_annually": float(e.price_annually),
        "currency": e.currency,
        "sort_order": e.sort_order,
        "is_public": e.is_public,
        "trial_day_count": e.trial_day_count,
        "is_trial_active": e.is_trial_active,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
    if include_features and hasattr(e, "features"):
        d["features"] = [_feature_dto(f) for f in e.features]
    return d


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/public")
async def list_public_editions(db: DBSession):
    """Anonymous — returns publicly visible editions with their features for paywall display."""
    svc = EditionsService(db)
    items = await svc.get_public()
    return {"items": [_edition_dto(e, include_features=True) for e in items], "total_count": len(items)}


@router.get("")
async def list_editions(db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    items = await svc.get_all()
    return {"items": [_edition_dto(e, include_features=True) for e in items], "total_count": len(items)}


@router.get("/for-select")
async def for_select(db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    return {"items": await svc.get_for_select()}


@router.post("/move-tenants")
async def move_tenants(body: MoveTenantsRequest, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    moved = await svc.move_tenants(body.source_edition_id, body.target_edition_id)
    return {"moved_count": moved}


@router.get("/{edition_id}")
async def get_edition(edition_id: uuid.UUID, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    return _edition_dto(await svc.get(edition_id), include_features=True)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_edition(body: CreateEditionRequest, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    edition = await svc.create(**body.model_dump())
    return _edition_dto(edition, include_features=True)


@router.put("/{edition_id}")
async def update_edition(edition_id: uuid.UUID, body: UpdateEditionRequest, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    edition = await svc.update(edition_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    return _edition_dto(edition, include_features=True)


@router.delete("/{edition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edition(edition_id: uuid.UUID, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    await svc.delete(edition_id)


@router.get("/{edition_id}/tenant-count")
async def get_tenant_count(edition_id: uuid.UUID, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    count = await svc.get_tenant_count(edition_id)
    return {"tenant_count": count}


# ── Feature management ────────────────────────────────────────────────────────

@router.get("/{edition_id}/features")
async def list_features(edition_id: uuid.UUID, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    features = await svc.get_features(edition_id)
    return {"items": [_feature_dto(f) for f in features]}


@router.post("/{edition_id}/features", status_code=status.HTTP_201_CREATED)
async def add_feature(edition_id: uuid.UUID, body: CreateFeatureRequest, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    feat = await svc.add_feature(edition_id, **body.model_dump())
    return _feature_dto(feat)


@router.put("/{edition_id}/features/replace")
async def replace_features(edition_id: uuid.UUID, body: List[ReplaceFeatureItem], db: DBSession, _: AdminUser):
    """Atomically replace all features for an edition."""
    svc = EditionsService(db)
    await svc.replace_features(edition_id, [f.model_dump() for f in body])
    edition = await svc.get(edition_id)
    return _edition_dto(edition, include_features=True)


@router.put("/{edition_id}/features/{feature_id}")
async def update_feature(
    edition_id: uuid.UUID, feature_id: uuid.UUID, body: UpdateFeatureRequest, db: DBSession, _: AdminUser
):
    svc = EditionsService(db)
    feat = await svc.update_feature(edition_id, feature_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    return _feature_dto(feat)


@router.delete("/{edition_id}/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature(edition_id: uuid.UUID, feature_id: uuid.UUID, db: DBSession, _: AdminUser):
    svc = EditionsService(db)
    await svc.delete_feature(edition_id, feature_id)

