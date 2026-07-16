"""Async SQLAlchemy database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from circleback.config import get_settings


def _build_engine(database_url: str | None = None):  # type: ignore[no-untyped-def]
    """Create an async engine. Accepts an explicit URL for testing."""
    url = database_url or get_settings().database_url
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )


engine = _build_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
