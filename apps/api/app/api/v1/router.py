from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    agents,
    analytics,
    auth,
    digests,
    governance,
    transactions,
    workspace,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(workspace.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(analytics.router)
api_router.include_router(agents.router)
api_router.include_router(governance.router)
api_router.include_router(digests.router)
