"""List tenants and users for login reference."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.domain.models.identity import IdentityUser, IdentityUserRole, IdentityRole
from app.domain.models.tenant import Tenant


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    sf = async_sessionmaker(engine)
    async with sf() as db:
        tenants = (await db.execute(select(Tenant).order_by(Tenant.name))).scalars().all()
        print("=== TENANTS ===")
        if not tenants:
            print("(none)")
        for t in tenants:
            print(f"  name: {t.name}")
            print(f"  normalized_name: {t.normalized_name}")
            print(f"  id: {t.id}")
            print(f"  active: {t.is_active}  admin_email: {t.admin_email_address or '—'}")
            print()

        users = (
            await db.execute(
                select(IdentityUser)
                .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
                .order_by(IdentityUser.email)
            )
        ).scalars().all()
        print("=== USERS (login with email or username) ===")
        for u in users:
            role_names = []
            for ur in u.roles or []:
                role = ur.role
                if role:
                    role_names.append(role.name)
            tenant_label = "(host — no tenant)"
            if u.tenant_id:
                match = next((t for t in tenants if t.id == u.tenant_id), None)
                tenant_label = f"{match.name} ({u.tenant_id})" if match else str(u.tenant_id)
            print(f"  {u.email}")
            print(f"    username: {u.user_name}")
            print(f"    tenant: {tenant_label}")
            print(f"    roles: {role_names or ['—']}")
            print(f"    active: {u.is_active}  confirmed: {u.email_confirmed}")
            print(f"    password_login: {'yes' if u.password_hash else 'no (SSO only?)'}")
            print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
