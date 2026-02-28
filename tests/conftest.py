"""Pytest fixtures."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base, get_session
from app.main import app
from app.services.vault import _encryptor


@pytest.fixture(autouse=True)
def _clear_settings_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Reset cached settings and point to test crypto key.

    Parameters
    ----------
    tmp_path : Path
        Temporary path fixture.
    monkeypatch : pytest.MonkeyPatch
        Environment monkeypatch helper.

    Yields
    ------
    None
        Applies environment overrides for each test.
    """
    get_settings.cache_clear()
    _encryptor.cache_clear()
    monkeypatch.setenv("AGENT_KEY_MASTER_KEY_PATH", str(tmp_path / "master.key"))
    yield
    get_settings.cache_clear()
    _encryptor.cache_clear()


@pytest.fixture()
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """Create a test HTTP client backed by SQLite.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory for test database.

    Yields
    ------
    AsyncClient
        Configured test client.
    """
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(database_url, future=True)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()
