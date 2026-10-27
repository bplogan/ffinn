"""
Paywall configuration routes — mirrors PaywallConfigurationController.cs.

GET /api/paywall/configuration  - anonymous (public pricing page data)
PUT /api/paywall/configuration  - admin: update paywall settings
GET /api/paywall/editions       - anonymous: editions with features for plan-selection UI
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.exceptions import BusinessException
from app.services.misc_services import SettingsService

router = APIRouter(prefix="/api/paywall", tags=["Paywall"])

_KEY_PREFIX = "Paywall."

_DEFAULTS: dict[str, str] = {
    "Enabled": "false",
    "Title": "Upgrade Your Plan",
    "Description": "Unlock powerful features with a subscription.",
    "PriceMonthly": "0.00",
    "PriceAnnually": "0.00",
    "Currency": "USD",
    "CtaText": "Subscribe Now",
    "Features": "[]",  # JSON array of feature strings
    "StripePriceIdMonthly": "",
    "StripePriceIdAnnually": "",
}


class PaywallConfigurationDto(BaseModel):
    enabled: bool = False
    title: str = "Upgrade Your Plan"
    description: str = "Unlock powerful features with a subscription."
    price_monthly: float = 0.0
    price_annually: float = 0.0
    currency: str = "USD"
    cta_text: str = "Subscribe Now"
    features: List[str] = []
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_annually: Optional[str] = None


async def _load_config(svc: SettingsService) -> dict[str, str]:
    rows = await svc.get_settings_by_prefix(_KEY_PREFIX, tenant_id=None)
    merged = dict(_DEFAULTS)
    for row in rows:
        short_key = row.key.removeprefix(_KEY_PREFIX)
        merged[short_key] = row.value
    return merged


def _to_dto(raw: dict[str, str]) -> PaywallConfigurationDto:
    import json
    features_raw = raw.get("Features", "[]")
    try:
        features_list: list[str] = json.loads(features_raw)
    except (ValueError, TypeError):
        features_list = []

    return PaywallConfigurationDto(
        enabled=raw.get("Enabled", "false").lower() == "true",
        title=raw.get("Title", _DEFAULTS["Title"]),
        description=raw.get("Description", _DEFAULTS["Description"]),
        price_monthly=float(raw.get("PriceMonthly", "0.00")),
        price_annually=float(raw.get("PriceAnnually", "0.00")),
        currency=raw.get("Currency", "USD"),
        cta_text=raw.get("CtaText", _DEFAULTS["CtaText"]),
        features=features_list,
        stripe_price_id_monthly=raw.get("StripePriceIdMonthly") or None,
        stripe_price_id_annually=raw.get("StripePriceIdAnnually") or None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/configuration", response_model=PaywallConfigurationDto)
async def get_configuration(db: DBSession):
    """Public endpoint — returns current paywall configuration."""
    svc = SettingsService(db)
    raw = await _load_config(svc)
    return _to_dto(raw)


@router.put("/configuration", status_code=204)
async def update_configuration(
    body: PaywallConfigurationDto,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    """Admin-only: update paywall configuration."""
    if not current_user.is_admin() or current_user.tenant_id is not None:
        raise BusinessException(
            "FORBIDDEN",
            "Only host administrators can update paywall configuration.",
        )

    import json
    svc = SettingsService(db)
    await svc.bulk_set_settings(
        [
            {"key": f"{_KEY_PREFIX}Enabled", "value": str(body.enabled).lower()},
            {"key": f"{_KEY_PREFIX}Title", "value": body.title},
            {"key": f"{_KEY_PREFIX}Description", "value": body.description},
            {"key": f"{_KEY_PREFIX}PriceMonthly", "value": str(body.price_monthly)},
            {"key": f"{_KEY_PREFIX}PriceAnnually", "value": str(body.price_annually)},
            {"key": f"{_KEY_PREFIX}Currency", "value": body.currency},
            {"key": f"{_KEY_PREFIX}CtaText", "value": body.cta_text},
            {"key": f"{_KEY_PREFIX}Features", "value": json.dumps(body.features)},
            {"key": f"{_KEY_PREFIX}StripePriceIdMonthly", "value": body.stripe_price_id_monthly or ""},
            {"key": f"{_KEY_PREFIX}StripePriceIdAnnually", "value": body.stripe_price_id_annually or ""},
        ],
        tenant_id=None,
    )
    return None


@router.get("/editions")
async def get_paywall_editions(db: DBSession):
    """Anonymous — returns public editions with features for the registration paywall."""
    from app.services.misc_services import EditionsService
    svc = EditionsService(db)
    items = await svc.get_public()

    def _feature_dto(f) -> dict:
        return {
            "id": str(f.id),
            "feature_name": f.feature_name,
            "display_name": f.display_name,
            "feature_value": f.feature_value,
            "is_included": f.is_included,
            "sort_order": f.sort_order,
        }

    return {
        "items": [
            {
                "id": str(e.id),
                "display_name": e.display_name,
                "is_free": e.is_free,
                "price_monthly": float(e.price_monthly),
                "price_annually": float(e.price_annually),
                "currency": e.currency,
                "sort_order": e.sort_order,
                "trial_day_count": e.trial_day_count,
                "is_trial_active": e.is_trial_active,
                "features": [_feature_dto(f) for f in e.features],
            }
            for e in items
        ]
    }
