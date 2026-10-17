from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import TenantContext, tenant_context
from app.database.models import AccountType, FinancialAccount
from app.database.session import get_session

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    external_reference: str = Field(min_length=1, max_length=128)
    account_type: AccountType = AccountType.UNKNOWN


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    external_reference: str
    account_type: AccountType


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[FinancialAccount]:
    result = await session.scalars(
        select(FinancialAccount)
        .where(FinancialAccount.tenant_id == context.tenant_id)
        .order_by(FinancialAccount.created_at)
    )
    return list(result)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    body: AccountCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FinancialAccount:
    account = FinancialAccount(tenant_id=context.tenant_id, **body.model_dump())
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account
