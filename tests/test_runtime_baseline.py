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


def test_database_dependency_yields_a_real_session(tmp_path):
    database_module._db = Database(f"sqlite:///{tmp_path / 'dependency.db'}")
    database_module._db.init()

    dependency = get_db()
    assert isinstance(dependency, Generator)
    session = next(dependency)
    assert isinstance(session, Session)
    assert session.execute(text("SELECT 1")).scalar_one() == 1
    dependency.close()


@pytest.mark.asyncio
async def test_health_probe_uses_sqlalchemy_2_execution(db_session):
    response = await health_check_db(db_session)
    assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_lifespan_initializes_arq_with_redis_settings(monkeypatch, tmp_path):
    captured: list[RedisSettings] = []

    class FakePool:
        async def close(self) -> None:
            pass

    async def fake_create_pool(settings):
        captured.append(settings)
        return FakePool()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'lifespan.db'}")
    monkeypatch.setenv("DEX_API_KEY", "test-dex")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setattr(api_main, "create_pool", fake_create_pool)

    async with api_main.lifespan(api_main.app):
        pass

    assert len(captured) == 1
    assert isinstance(captured[0], RedisSettings)
    assert captured[0].host == "redis.internal"
    assert captured[0].port == 6380


def test_graphql_router_is_mounted():
    assert any(route.path == "/api/graphql" for route in api_main.app.routes)

