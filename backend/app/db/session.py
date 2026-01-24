# backend/app/db/session.py

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config.settings import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(autoflush=False, bind=engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get a database session."""
    async with AsyncSessionLocal() as session:
        yield session
