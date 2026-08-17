# E-Wallet API & PaySphere Dashboard v1.1.1
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import redis_client
from app.api.v1.router import api_router

# Ensure all models are loaded for metadata creation
import app.models  # noqa

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Try initializing database tables without crashing Uvicorn server on failure
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database connection and tables initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization warning on startup (will retry on requests): {e}")

    yield

    # Shutdown: Close connections safely
    try:
        await engine.dispose()
    except Exception:
        pass

    try:
        await redis_client.close()
    except Exception:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Enable CORS for Frontend Applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API V1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    db_healthy = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False

    redis_healthy = False
    try:
        redis_healthy = await redis_client.ping()
    except Exception:
        redis_healthy = False

    return {
        "status": "healthy",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected",
    }


# Mount Static Frontend Web App at Root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
