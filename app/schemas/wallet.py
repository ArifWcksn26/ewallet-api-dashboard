from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.transaction import TransactionType, TransactionStatus, LedgerType


class WalletOut(BaseModel):
    id: str
    user_id: str
    balance: Decimal
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileWalletOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    wallet_id: str
    balance: Decimal
    currency: str
    has_pin: bool = False
    cached: bool = False


class TopupRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=18, decimal_places=2)
    description: str | None = Field(default="Top-up Saldo", max_length=255)


class TransferRequest(BaseModel):
    receiver_wallet_id: str = Field(..., min_length=36, max_length=36)
    amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=18, decimal_places=2)
    description: str | None = Field(default="Transfer Dana", max_length=255)
    pin: str | None = Field(default=None, min_length=6, max_length=6)


class LedgerOut(BaseModel):
    id: str
    wallet_id: str
    entry_type: LedgerType
    amount: Decimal
    balance_after: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionOut(BaseModel):
    id: str
    reference_id: str
    type: TransactionType
    status: TransactionStatus
    amount: Decimal
    description: str | None
    created_at: datetime
    ledger_entry: LedgerOut | None = None

    model_config = ConfigDict(from_attributes=True)


class HistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[TransactionOut]
