from __future__ import annotations

from collections.abc import Generator

import pytest
from arq.connections import RedisSettings
from sqlalchemy import text
from sqlalchemy.orm import Session

import core.database as database_module
from api import main as api_main
from api.routes.health import health_check_db
from core.database import Database, get_db


@pytest.mark.asyncio
async def test_lifespan_refuses_missing_private_auth_configuration(monkeypatch):
    monkeypatch.setenv("DEX_API_KEY", "test-dex")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
    monkeypatch.delenv("ULTRADEX_API_TOKEN", raising=False)
    monkeypatch.delenv("ULTRADEX_OPERATOR_ID", raising=False)

    with pytest.raises(ValueError, match="Missing private auth configuration"):
        async with api_main.lifespan(api_main.app):
            pass


@pytest.mark.asyncio
async def test_lifespan_closes_database_when_redis_startup_fails(monkeypatch, tmp_path):
    database_closed = False

    async def failing_create_pool(_settings):
        raise ConnectionError("redis unavailable")

    def fake_close_database():
        nonlocal database_closed
        database_closed = True

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'startup.db'}")
    monkeypatch.setenv("DEX_API_KEY", "test-dex")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
    monkeypatch.setenv("ULTRADEX_API_TOKEN", "test-api-key")
    monkeypatch.setenv("ULTRADEX_OPERATOR_ID", "operator:test")
    monkeypatch.setattr(api_main, "create_pool", failing_create_pool)
    monkeypatch.setattr(api_main, "close_database", fake_close_database)

    with pytest.raises(ConnectionError, match="redis unavailable"):
        async with api_main.lifespan(api_main.app):
            pass

    assert database_closed is True


def test_database_dependency_yields_a_real_session(tmp_path):
    database_module._db = Database(f"sqlite:///{tmp_path / 'dependency.db'}")
    database_module._db.init()

    dependency = get_db()
    assert isinstance(dependency, Generator)
    session = next(dependency)
    assert isinstance(session, Session)
    assert session.get_bind() is database_module._db.engine
    assert session.execute(text("SELECT 1")).scalar_one() == 1
    dependency.close()


@pytest.mark.asyncio
async def test_health_probe_uses_sqlalchemy_2_execution(db_session):
    response = await health_check_db(db_session)
    assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_lifespan_initializes_arq_with_redis_settings(monkeypatch, tmp_path):
    captured: list[RedisSettings] = []
    database_closed = False

    class FakePool:
        async def close(self) -> None:
            pass

    async def fake_create_pool(settings):
        captured.append(settings)
        return FakePool()

    def fake_close_database():
        nonlocal database_closed
        database_closed = True

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'lifespan.db'}")
    monkeypatch.setenv("DEX_API_KEY", "test-dex")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
    monkeypatch.setenv("ULTRADEX_API_TOKEN", "test-api-key")
    monkeypatch.setenv("ULTRADEX_OPERATOR_ID", "operator:test")
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6380/4")
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)
    monkeypatch.setattr(api_main, "create_pool", fake_create_pool)
    monkeypatch.setattr(api_main, "close_database", fake_close_database, raising=False)

    async with api_main.lifespan(api_main.app):
        pass

    assert len(captured) == 1
    assert isinstance(captured[0], RedisSettings)
    assert captured[0].host == "redis.internal"
    assert captured[0].port == 6380
    assert captured[0].database == 4
    assert database_closed is True


def test_graphql_router_is_mounted():
    assert any(route.path == "/api/graphql" for route in api_main.app.routes)
