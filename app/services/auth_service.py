from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserOut
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token


class AuthService:
    @staticmethod
    async def register(db: AsyncSession, user_in: UserCreate) -> UserOut:
        # Check if email already exists
        stmt = select(User).where(User.email == user_in.email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email sudah terdaftar.",
            )

        # Create User & Auto-create Wallet in atomic transaction
        hashed_pwd = hash_password(user_in.password)
        new_user = User(
            email=user_in.email,
            password_hash=hashed_pwd,
            full_name=user_in.full_name,
        )
        db.add(new_user)
        await db.flush()  # Generate user.id

        new_wallet = Wallet(user_id=new_user.id)
        db.add(new_wallet)

        await db.commit()
        await db.refresh(new_user)
        return UserOut.model_validate(new_user)

    @staticmethod
    async def login(db: AsyncSession, credentials: UserLogin) -> TokenResponse:
        stmt = select(User).where(User.email == credentials.email, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah.",
            )

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
