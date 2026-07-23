from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from core.models import Base, get_engine, get_session_factory


@pytest.fixture(autouse=True)
def private_auth_configuration(monkeypatch):
    monkeypatch.setenv("ULTRADEX_API_TOKEN", "test-api-key")
    monkeypatch.setenv("ULTRADEX_OPERATOR_ID", "operator:test")


class FakeRedis:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[object, ...]]] = []

    async def enqueue_job(self, task_name: str, *args: object) -> None:
        self.enqueued.append((task_name, args))


class FailingRedis:
    async def enqueue_job(self, task_name: str, *args: object) -> None:
        raise ConnectionError("queue unavailable")


@pytest.fixture
def db_session(tmp_path) -> Iterator[Session]:
    database_url = f"sqlite:///{tmp_path / 'ultradex-test.db'}"
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    session = get_session_factory(database_url)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()
