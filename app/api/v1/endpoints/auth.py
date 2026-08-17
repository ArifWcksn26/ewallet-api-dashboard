from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserOut
from app.schemas.beneficiary import PINSetupRequest
from app.services.auth_service import AuthService
from app.services.wallet_service import WalletService
from app.core.security import hash_password

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Pendaftaran akun pengguna baru."""
    return await AuthService.register(db, user_in)


@router.post("/login", response_model=TokenResponse)
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    """Autentikasi pengguna & pengembalian token JWT."""
    return await AuthService.login(db, user_in)


@router.post("/pin")
async def setup_transaction_pin(
    request: PINSetupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Setel atau perbarui 6-digit PIN Keuangan pengguna."""
    current_user.transaction_pin_hash = hash_password(request.pin)
    await db.commit()
    await WalletService.invalidate_wallet_cache([current_user.id])
    return {"message": "PIN Keuangan 6-digit berhasil disimpan."}
