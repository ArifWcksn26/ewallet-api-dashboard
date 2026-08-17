from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_db, get_current_user
from app.models.user import User
from app.models.beneficiary import Beneficiary
from app.schemas.beneficiary import BeneficiaryCreate, BeneficiaryOut

router = APIRouter()


@router.get("", response_model=list[BeneficiaryOut])
async def list_beneficiaries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dapatkan daftar kontak penerima favorit yang disimpan."""
    stmt = (
        select(Beneficiary)
        .where(Beneficiary.user_id == current_user.id)
        .order_by(Beneficiary.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=BeneficiaryOut, status_code=status.HTTP_201_CREATED)
async def add_beneficiary(
    request: BeneficiaryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simpan kontak penerima favorit baru."""
    stmt = select(Beneficiary).where(
        Beneficiary.user_id == current_user.id,
        Beneficiary.target_wallet_id == request.target_wallet_id,
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID Dompet ini sudah ada di daftar kontak favorit Anda.",
        )

    b = Beneficiary(
        user_id=current_user.id,
        nickname=request.nickname,
        target_wallet_id=request.target_wallet_id,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b


@router.delete("/{beneficiary_id}")
async def delete_beneficiary(
    beneficiary_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hapus kontak penerima dari daftar favorit."""
    stmt = select(Beneficiary).where(
        Beneficiary.id == beneficiary_id,
        Beneficiary.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    b = res.scalar_one_or_none()
    if not b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kontak tidak ditemukan.",
        )

    await db.delete(b)
    await db.commit()
    return {"message": "Kontak berhasil dihapus."}
