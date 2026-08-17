import asyncio
import logging
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Retry connecting to DB on cloud cold starts
    max_retries = 10
    retry_delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database connection and tables initialized successfully.")
            break
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise e
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed ({e}). Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)

    yield

    # Shutdown: Close connections
    await engine.dispose()
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
