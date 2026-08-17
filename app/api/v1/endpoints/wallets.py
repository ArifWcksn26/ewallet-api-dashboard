from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, get_current_user, get_idempotency_key
from app.models.user import User
from app.schemas.wallet import (
    UserProfileWalletOut,
    TopupRequest,
    TransferRequest,
    TransactionOut,
    HistoryResponse,
)
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallets", tags=["Wallets"])


@router.get("/me", response_model=UserProfileWalletOut)
async def get_my_wallet_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cek saldo & profil wallet pengguna terautentikasi (cached via Redis dengan TTL singkat).
    """
    return await WalletService.get_user_wallet_profile(db, current_user)


@router.post("/topup", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def topup(
    request: TopupRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: str = Depends(get_idempotency_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Tambah saldo dompet (Top-up).
    - Membutuhkan header `Idempotency-Key` (mencegah penambahan saldo ganda).
    - Menjalankan transaksi atomic DB & pencatatan Single/Double Entry Ledger.
    """
    return await WalletService.topup_wallet(db, current_user, request, idempotency_key)


@router.post("/transfer", response_model=TransactionOut, status_code=status.HTTP_200_OK)
async def transfer(
    request: TransferRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: str = Depends(get_idempotency_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Transfer dana antar pengguna.
    - Membutuhkan header `Idempotency-Key` (Redis cache 24 jam).
    - Menggunakan **Pessimistic Locking (`SELECT FOR UPDATE`)** dengan urutan ID yang konsisten untuk mengantisipasi deadlock.
    - **Double-Entry Accounting**: Mencatat 2 baris ledger (DEBIT untuk pengirim, CREDIT untuk penerima).
    - Atomic DB Transaction (BEGIN...COMMIT/ROLLBACK).
    """
    return await WalletService.transfer_wallet(db, current_user, request, idempotency_key)


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    page: int = Query(default=1, ge=1, description="Nomor halaman"),
    limit: int = Query(default=10, ge=1, le=100, description="Jumlah item per halaman"),
    start_date: datetime | None = Query(default=None, description="Filter tanggal mulai (ISO Format)"),
    end_date: datetime | None = Query(default=None, description="Filter tanggal akhir (ISO Format)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mendapatkan riwayat mutasi mutlak dompet pengguna.
    - Dilengkapi dengan Pagination & Filter Rentang Tanggal.
    """
    return await WalletService.get_transaction_history(
        db, current_user, page=page, limit=limit, start_date=start_date, end_date=end_date
    )
