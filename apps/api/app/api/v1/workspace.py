"""Passwordless provisioning for an isolated FinPilot statement workspace."""

from secrets import token_hex, token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.auth.tokens import create_access_token
from app.core.settings import Settings, get_settings
from app.database.models import Membership, Tenant, TenantRole, User
from app.database.session import get_session
from app.schemas.auth import TokenResponse
from app.services.governance import ensure_governance_baseline

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_workspace(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Create an isolated workspace without accepting user credentials or ledger data."""
    identity = token_hex(12)
    user = User(
        email=f"synthetic-{identity}@example.invalid",
        password_hash=hash_password(token_urlsafe(32)),
    )
    tenant = Tenant(name="Private statement workspace", slug=f"workspace-{identity}")
    session.add_all([user, tenant])
    await session.flush()
    session.add(Membership(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER))
    await ensure_governance_baseline(
        session, tenant_id=tenant.id, owner_user_id=user.id, settings=settings
    )
    await session.commit()
    return TokenResponse(access_token=create_access_token(user.id, settings))
