from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Wallet API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: Optional[str] = None
    DATABASE_PUBLIC_URL: Optional[str] = None
    DATABASE_PRIVATE_URL: Optional[str] = None
    POSTGRES_URL: Optional[str] = None
    POSTGRES_PRIVATE_URL: Optional[str] = None

    REDIS_URL: Optional[str] = None
    REDIS_PRIVATE_URL: Optional[str] = None
    REDIS_PUBLIC_URL: Optional[str] = None

    JWT_SECRET_KEY: str = "supersecretjwtkey1234567890123456"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        raw_url = (
            self.DATABASE_PRIVATE_URL
            or self.DATABASE_URL
            or self.POSTGRES_PRIVATE_URL
            or self.POSTGRES_URL
            or self.DATABASE_PUBLIC_URL
            or "postgresql+asyncpg://postgres:secretpassword@localhost:5432/ewallet_db"
        )
        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+asyncpg://"):
            raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Strip libpq sslmode query string parameters unsupported by asyncpg URL parser
        if "?" in raw_url:
            base_url, query = raw_url.split("?", 1)
            query_params = [p for p in query.split("&") if not p.startswith("sslmode=") and not p.startswith("ssl=")]
            raw_url = base_url + ("?" + "&".join(query_params) if query_params else "")

        return raw_url

    @property
    def ASYNC_REDIS_URL(self) -> str:
        return (
            self.REDIS_PRIVATE_URL
            or self.REDIS_URL
            or self.REDIS_PUBLIC_URL
            or "redis://:redispassword@localhost:6379/0"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
