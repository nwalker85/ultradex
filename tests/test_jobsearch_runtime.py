from __future__ import annotations

import inspect

import pytest

from api import dependencies
from api import main as api_main
from core.jobsearch_nats import UnavailableJobSearchPublisher
from core.jobsearch_worker import JobSearchPullConsumer, run_jobsearch_worker


class FakeRedis:
    async def close(self):
        pass


def _runtime_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'runtime.db'}")
    monkeypatch.setenv("DEX_API_KEY", "test-dex")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
    monkeypatch.setenv("ULTRADEX_API_TOKEN", "test-api-key")
    monkeypatch.setenv("ULTRADEX_OPERATOR_ID", "operator:test")


@pytest.mark.asyncio
async def test_lifespan_connects_and_closes_configured_jobsearch_nats(
    monkeypatch,
    tmp_path,
):
    _runtime_env(monkeypatch, tmp_path)
    monkeypatch.setenv("NATS_URL", "nats://nats.internal:4222")
    state = {"connected": 0, "closed": 0, "url": None}

    class Publisher:
        def __init__(self, *, url):
            state["url"] = url

        async def connect(self):
            state["connected"] += 1

        async def close(self):
            state["closed"] += 1

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(api_main, "create_pool", fake_create_pool)
    monkeypatch.setattr(api_main, "JobSearchNATSPublisher", Publisher)

    async with api_main.lifespan(api_main.app):
        assert dependencies.get_jobsearch_publisher().__class__ is Publisher
        assert dependencies.get_receipt_issuer().public_key_bytes

    assert state == {
        "connected": 1,
        "closed": 1,
        "url": "nats://nats.internal:4222",
    }


@pytest.mark.asyncio
async def test_lifespan_without_nats_keeps_api_up_with_governed_unavailable_port(
    monkeypatch,
    tmp_path,
):
    _runtime_env(monkeypatch, tmp_path)
    monkeypatch.delenv("NATS_URL", raising=False)

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(api_main, "create_pool", fake_create_pool)
    async with api_main.lifespan(api_main.app):
        publisher = dependencies.get_jobsearch_publisher()
        assert isinstance(publisher, UnavailableJobSearchPublisher)
        with pytest.raises(ConnectionError, match="not configured"):
            await publisher.publish_command(None)


def test_worker_runtime_is_a_real_pull_consumer_not_an_arq_alias():
    assert inspect.iscoroutinefunction(run_jobsearch_worker)
    assert inspect.iscoroutinefunction(JobSearchPullConsumer.run_forever)
    assert inspect.iscoroutinefunction(JobSearchPullConsumer.close)


def test_compose_adds_nats_and_jobsearch_worker_without_replacing_arq():
    compose = (
        __import__("pathlib").Path(__file__).parents[1] / "docker-compose.yml"
    ).read_text()
    assert "\n  nats:\n" in compose
    assert "\n  worker:\n" in compose
    assert "python -m arq core.workers.WorkerSettings" in compose
    assert "\n  jobsearch-worker:\n" in compose
    assert "python -m core.jobsearch_worker" in compose
    assert "NATS_URL: nats://nats:4222" in compose
