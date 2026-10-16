import re
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import current_user
from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import create_access_token
from app.core.settings import Settings, get_settings
from app.database.models import Membership, Tenant, TenantRole, User
from app.database.session import get_session
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TenantSummary,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "household"
    return f"{base}-{uuid4().hex[:8]}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    tenant = Tenant(name=body.household_name, slug=_slugify(body.household_name))
    session.add_all([user, tenant])
    await session.flush()
    session.add(Membership(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        ) from exc
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=UserResponse)
async def me(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    loaded = await session.scalar(
        select(User)
        .options(selectinload(User.memberships).selectinload(Membership.tenant))
        .where(User.id == user.id)
    )
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    return UserResponse(
        id=loaded.id,
        email=loaded.email,
        tenants=[
            TenantSummary(
                id=membership.tenant.id,
                name=membership.tenant.name,
                slug=membership.tenant.slug,
                role=membership.role.value,
            )
            for membership in loaded.memberships
        ],
    )
