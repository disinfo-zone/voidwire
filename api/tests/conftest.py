"""API test configuration."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from api.dependencies import get_db, require_admin
from api.main import create_app
from httpx import ASGITransport, AsyncClient


class FakeAdminUser:
    """Minimal stand-in for AdminUser model."""

    id = "test-admin-id"
    username = "testadmin"
    email = "admin@test.local"
    is_active = True
    role = "admin"


def _fake_admin():
    return FakeAdminUser()


@pytest.fixture
def app():
    a = create_app()
    a.state._setup_complete = True
    a.state._setup_checked_at = time.monotonic()
    a.dependency_overrides[require_admin] = _fake_admin
    return a


@pytest.fixture
def mock_db():
    """Creates a mock AsyncSession with common patterns pre-configured."""
    session = AsyncMock()
    # AsyncSession.add() is synchronous; use MagicMock to avoid un-awaited coroutine warnings.
    session.add = MagicMock()
    # Default: execute returns empty result set
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    empty_result.scalars.return_value.first.return_value = None
    empty_result.scalar.return_value = 0
    empty_result.all.return_value = []
    empty_result.rowcount = 0
    session.execute.return_value = empty_result
    # Default: get returns None
    session.get.return_value = None
    return session


@pytest.fixture
async def client(app, mock_db):
    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def unauthenticated_client():
    """Client with NO auth override -- tests that endpoints require auth."""
    a = create_app()
    a.state._setup_complete = True
    a.state._setup_checked_at = time.monotonic()
    transport = ASGITransport(app=a)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
