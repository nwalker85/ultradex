from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from core import CommandRequest, GatewayService, IdempotencyConflictError, OperationDB
from core.models import Base, get_engine, get_session_factory
from tests.conftest import FakeRedis


def test_equivalent_concurrent_submissions_share_one_operation(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'concurrent.db'}"
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    barrier = Barrier(2)

    def submit() -> tuple[str, int]:
        session = get_session_factory(database_url)()
        redis = FakeRedis()
        try:
            barrier.wait()
            operation = asyncio.run(
                GatewayService(redis).submit_command(
                    session,
                    CommandRequest(
                        command="analyze",
                        parameters={"limit": 5},
                        actor_id="operator:test",
                        idempotency_key="concurrent-key",
                    ),
                )
            )
            return operation.id, len(redis.enqueued)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: submit(), range(2)))

        verification = get_session_factory(database_url)()
        try:
            assert len({operation_id for operation_id, _ in results}) == 1
            assert sum(enqueued for _, enqueued in results) == 1
            assert verification.query(OperationDB).count() == 1
        finally:
            verification.close()
    finally:
        engine.dispose()


def test_conflicting_concurrent_submissions_leave_no_orphan_operation(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'conflict.db'}"
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    barrier = Barrier(2)

    def submit(limit: int) -> tuple[str, int]:
        session = get_session_factory(database_url)()
        redis = FakeRedis()
        try:
            barrier.wait()
            try:
                asyncio.run(
                    GatewayService(redis).submit_command(
                        session,
                        CommandRequest(
                            command="analyze",
                            parameters={"limit": limit},
                            actor_id="operator:test",
                            idempotency_key="conflicting-key",
                        ),
                    )
                )
                return "accepted", len(redis.enqueued)
            except IdempotencyConflictError:
                return "conflict", len(redis.enqueued)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, (5, 6)))

        verification = get_session_factory(database_url)()
        try:
            assert sorted(status for status, _ in results) == ["accepted", "conflict"]
            assert sum(enqueued for _, enqueued in results) == 1
            assert verification.query(OperationDB).count() == 1
        finally:
            verification.close()
    finally:
        engine.dispose()
