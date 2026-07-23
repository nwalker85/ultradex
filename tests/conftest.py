from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from core.models import Base, get_engine, get_session_factory
from core.jobsearch_receipts import ReceiptIssuer


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


class FakeJobSearchPublisher:
    def __init__(self, *, fail_commands: bool = False) -> None:
        self.fail_commands = fail_commands
        self.commands: list[object] = []
        self.events: list[object] = []

    async def publish_command(self, command) -> None:
        if self.fail_commands:
            raise ConnectionError("NATS unavailable")
        self.commands.append(command)

    async def publish_lifecycle(self, event) -> None:
        self.events.append(event)


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


@pytest.fixture
def receipt_issuer() -> ReceiptIssuer:
    return ReceiptIssuer(
        hmac_key=b"h" * 32,
        signing_private_key=bytes(range(32)),
        key_id=f"pairwise:v1:{'A' * 22}",
        executor_pairwise_id=f"pairwise:v1:{'B' * 22}",
    )


@pytest.fixture
def fake_jobsearch_publisher() -> FakeJobSearchPublisher:
    return FakeJobSearchPublisher()
