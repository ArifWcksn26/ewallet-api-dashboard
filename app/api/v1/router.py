from fastapi import APIRouter
from app.api.v1.endpoints import auth, wallets, beneficiaries

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(wallets.router, tags=["Wallets"])
api_router.include_router(beneficiaries.router, prefix="/beneficiaries", tags=["Beneficiaries"])
