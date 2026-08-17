from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class BeneficiaryCreate(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=100)
    target_wallet_id: str = Field(..., min_length=36, max_length=36)


class BeneficiaryOut(BaseModel):
    id: str
    nickname: str
    target_wallet_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PINSetupRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")


class PINVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
