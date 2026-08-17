from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import redis_client
from app.api.v1.router import api_router

# Ensure all models are loaded for metadata creation
import app.models  # noqa


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: Close connections
    await engine.dispose()
    await redis_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Enable CORS for Frontend Applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Bisa disesuaikan dengan URL frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API V1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    # Test Redis connection
    redis_healthy = False
    try:
        redis_healthy = await redis_client.ping()
    except Exception:
        redis_healthy = False

    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected" if redis_healthy else "disconnected",
    }


# Mount Static Frontend Web App at Root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
