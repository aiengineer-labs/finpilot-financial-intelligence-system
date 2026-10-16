from fastapi import APIRouter

from app.api.v1 import accounts, auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
