import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-secret-key")
os.environ.setdefault("DEBUG", "true")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Headers
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


def get_cookie(headers: Headers, name: str) -> str:
    for header in headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header.split(";")[0][len(name) + 1:]
    raise AssertionError(f"cookie {name!r} not found in {headers.get_list('set-cookie')}")


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s