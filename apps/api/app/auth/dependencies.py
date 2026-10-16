from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import decode_access_token
from app.core.settings import Settings, get_settings
from app.database.models import Membership, TenantRole, User
from app.database.session import get_session

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class TenantContext:
    user: User
    tenant_id: UUID
    role: TenantRole


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
        )
    try:
        claims = decode_access_token(credentials.credentials, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = await session.scalar(select(User).where(User.id == claims.sub, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="account unavailable")
    return user


async def tenant_context(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    x_tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
) -> TenantContext:
    membership = await session.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == x_tenant_id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    return TenantContext(user=user, tenant_id=x_tenant_id, role=membership.role)
