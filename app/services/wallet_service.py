import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.redis import redis_client
from app.core.security import verify_password
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction, LedgerEntry, TransactionType, TransactionStatus, LedgerType
from app.schemas.wallet import (
    UserProfileWalletOut,
    TopupRequest,
    TransferRequest,
    TransactionOut,
    LedgerOut,
    HistoryResponse,
)

CACHE_TTL_PROFILE = 10  # Cache profile & balance Redis TTL (detik)
IDEMPOTENCY_TTL = 86400  # 24 Jam (detik)


class WalletService:
    @staticmethod
    async def get_user_wallet(db: AsyncSession, user_id: str) -> Wallet:
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        result = await db.execute(stmt)
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet tidak ditemukan untuk pengguna ini.",
            )
        return wallet

    @staticmethod
    async def get_user_wallet_profile(db: AsyncSession, user: User) -> UserProfileWalletOut:
        cache_key = f"wallet:profile:{user.id}"
        cached_data = await redis_client.get(cache_key)

        if cached_data:
            data = json.loads(cached_data)
            data["cached"] = True
            return UserProfileWalletOut(**data)

        wallet = await WalletService.get_user_wallet(db, user.id)

        profile_data = {
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "wallet_id": wallet.id,
            "balance": str(wallet.balance),
            "currency": wallet.currency,
            "has_pin": bool(user.transaction_pin_hash),
        }

        # Cache in Redis with short TTL (10s)
        await redis_client.set(cache_key, json.dumps(profile_data), ex=CACHE_TTL_PROFILE)

        profile_data["cached"] = False
        return UserProfileWalletOut(**profile_data)

    @staticmethod
    async def invalidate_wallet_cache(user_ids: list[str]):
        """Hapus cache Redis profil wallet."""
        for u_id in user_ids:
            await redis_client.delete(f"wallet:profile:{u_id}")

    @staticmethod
    async def topup_wallet(
        db: AsyncSession, user: User, request: TopupRequest, idempotency_key: str
    ) -> TransactionOut:
        redis_idem_key = f"idempotency:{idempotency_key}"

        # 1. Cek Idempotency di Redis
        cached_res = await redis_client.get(redis_idem_key)
        if cached_res:
            data = json.loads(cached_res)
            return TransactionOut(**data)

        try:
            # 2. Start Atomic Transaction & Pessimistic Lock
            # Lock wallet pengguna
            stmt = select(Wallet).where(Wallet.user_id == user.id).with_for_update()
            result = await db.execute(stmt)
            wallet = result.scalar_one_or_none()

            if not wallet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet tidak ditemukan.",
                )

            # Update saldo wallet
            wallet.balance += request.amount

            # Buat transaksi
            ref_id = f"TOP-{uuid.uuid4().hex[:12].upper()}"
            tx = Transaction(
                reference_id=ref_id,
                idempotency_key=idempotency_key,
                type=TransactionType.TOPUP,
                status=TransactionStatus.COMPLETED,
                amount=request.amount,
                description=request.description,
            )
            db.add(tx)
            await db.flush()

            # Buat 1 baris Ledger (CREDIT)
            ledger = LedgerEntry(
                transaction_id=tx.id,
                wallet_id=wallet.id,
                entry_type=LedgerType.CREDIT,
                amount=request.amount,
                balance_after=wallet.balance,
            )
            db.add(ledger)

            await db.commit()
            await db.refresh(tx)

            res_schema = TransactionOut(
                id=tx.id,
                reference_id=tx.reference_id,
                type=tx.type,
                status=tx.status,
                amount=tx.amount,
                description=tx.description,
                created_at=tx.created_at,
                ledger_entry=LedgerOut.model_validate(ledger),
            )

            # Simpan hasil di Redis untuk Idempotency (24 Jam)
            res_dict = res_schema.model_dump(mode="json")
            await redis_client.set(redis_idem_key, json.dumps(res_dict), ex=IDEMPOTENCY_TTL)

            # Invalidate Cache Profil
            await WalletService.invalidate_wallet_cache([user.id])

            return res_schema

        except Exception as e:
            await db.rollback()
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gagal memproses topup: {str(e)}",
            )

    @staticmethod
    async def transfer_wallet(
        db: AsyncSession, sender_user: User, request: TransferRequest, idempotency_key: str
    ) -> TransactionOut:
        redis_idem_key = f"idempotency:{idempotency_key}"

        # 1. Cek Idempotency di Redis (24 Jam)
        cached_res = await redis_client.get(redis_idem_key)
        if cached_res:
            data = json.loads(cached_res)
            return TransactionOut(**data)

        # Dapatkan dompet milik pengirim
        stmt_w = select(Wallet).where(Wallet.user_id == sender_user.id)
        sender_w_res = await db.execute(stmt_w)
        sender_wallet = sender_w_res.scalar_one_or_none()
        if not sender_wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dompet Anda tidak ditemukan.",
            )

        # Cek PIN jika pengguna sudah memasang PIN
        if sender_user.transaction_pin_hash:
            if not request.pin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PIN Keuangan 6-digit wajib disertakan untuk melakukan transfer.",
                )
            if not verify_password(request.pin, sender_user.transaction_pin_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="PIN Keuangan yang Anda masukkan salah.",
                )

        if sender_wallet.id == request.receiver_wallet_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak dapat melakukan transfer ke dompet sendiri.",
            )

        try:
            # 2. Pessimistic Lock dengan Urutan ID Konsisten (Penting untuk Mencegah Deadlock)
            wallet_ids = sorted([sender_wallet.id, request.receiver_wallet_id])

            stmt = (
                select(Wallet)
                .where(Wallet.id.in_(wallet_ids))
                .with_for_update()
            )
            result = await db.execute(stmt)
            locked_wallets = {w.id: w for w in result.scalars().all()}

            if len(locked_wallets) < 2:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dompet penerima tidak ditemukan.",
                )

            s_wallet = locked_wallets[sender_wallet.id]
            r_wallet = locked_wallets[request.receiver_wallet_id]

            # Cek Saldo Cukup
            if s_wallet.balance < request.amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Saldo tidak mencukupi untuk melakukan transfer ini.",
                )

            # Mutasi Saldo
            s_wallet.balance -= request.amount
            r_wallet.balance += request.amount

            # Buat Record Transaksi Utama
            ref_id = f"TRF-{uuid.uuid4().hex[:12].upper()}"
            tx = Transaction(
                reference_id=ref_id,
                idempotency_key=idempotency_key,
                type=TransactionType.TRANSFER,
                status=TransactionStatus.COMPLETED,
                amount=request.amount,
                description=request.description,
            )
            db.add(tx)
            await db.flush()

            # 3. Double-Entry Accounting: 2 Baris Ledger (DEBIT untuk Pengirim, CREDIT untuk Penerima)
            sender_ledger = LedgerEntry(
                transaction_id=tx.id,
                wallet_id=s_wallet.id,
                entry_type=LedgerType.DEBIT,
                amount=request.amount,
                balance_after=s_wallet.balance,
            )

            receiver_ledger = LedgerEntry(
                transaction_id=tx.id,
                wallet_id=r_wallet.id,
                entry_type=LedgerType.CREDIT,
                amount=request.amount,
                balance_after=r_wallet.balance,
            )

            db.add(sender_ledger)
            db.add(receiver_ledger)

            # Atomic COMMIT
            await db.commit()
            await db.refresh(tx)

            res_schema = TransactionOut(
                id=tx.id,
                reference_id=tx.reference_id,
                type=tx.type,
                status=tx.status,
                amount=tx.amount,
                description=tx.description,
                created_at=tx.created_at,
                ledger_entry=LedgerOut.model_validate(sender_ledger),
            )

            # Simpan hasil di Redis untuk Idempotency (24 Jam)
            res_dict = res_schema.model_dump(mode="json")
            await redis_client.set(redis_idem_key, json.dumps(res_dict), ex=IDEMPOTENCY_TTL)

            # Invalidate Cache Profil Pengirim & Penerima
            await WalletService.invalidate_wallet_cache([s_wallet.user_id, r_wallet.user_id])

            return res_schema

        except Exception as e:
            await db.rollback()
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gagal memproses transfer: {str(e)}",
            )

    @staticmethod
    async def get_transaction_history(
        db: AsyncSession,
        user: User,
        page: int = 1,
        limit: int = 10,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> HistoryResponse:
        wallet = await WalletService.get_user_wallet(db, user.id)

        # Base query filter pada ledger_entries milik wallet user ini
        filters = [LedgerEntry.wallet_id == wallet.id]
        if start_date:
            filters.append(LedgerEntry.created_at >= start_date)
        if end_date:
            filters.append(LedgerEntry.created_at <= end_date)

        # Count total items
        count_stmt = select(func.count(LedgerEntry.id)).where(*filters)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # Query dengan pagination & filter tanggal
        offset = (page - 1) * limit
        stmt = (
            select(LedgerEntry)
            .options(selectinload(LedgerEntry.transaction))
            .where(*filters)
            .order_by(LedgerEntry.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(stmt)
        ledger_entries = result.scalars().all()

        items = []
        for entry in ledger_entries:
            tx = entry.transaction
            items.append(
                TransactionOut(
                    id=tx.id,
                    reference_id=tx.reference_id,
                    type=tx.type,
                    status=tx.status,
                    amount=tx.amount,
                    description=tx.description,
                    created_at=entry.created_at,
                    ledger_entry=LedgerOut.model_validate(entry),
                )
            )

        return HistoryResponse(
            total=total,
            page=page,
            limit=limit,
            items=items,
        )
