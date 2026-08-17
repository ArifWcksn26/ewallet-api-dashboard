import asyncio
import logging
from app.core.database import engine, Base
import app.models  # noqa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
