from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from nats.js.errors import APIError, NotFoundError
from ravenhelm_contracts import CorrelationContextV1, JobSearchCommandV1
from ravenhelm_contracts.jobsearch_v1 import COMMAND_NAMES_V1

from core.jobsearch_nats import (
    COMMAND_SUBJECTS,
    EVENT_SUBJECT_PREFIX,
    JobSearchNATSPublisher,
    REQUIRED_STREAM_SUBJECTS,
    STREAM_NAME,
    ensure_jobsearch_stream,
    lifecycle_subject,
)


class FakeJetStream:
    def __init__(self):
        self.published = []

    async def publish(self, subject, payload, headers=None):
        self.published.append((subject, payload, headers))


class FakeStreamConfig:
    def __init__(self, subjects):
        self.subjects = subjects

    def evolve(self, **changes):
        return FakeStreamConfig(changes.get("subjects", self.subjects))


class FakeStreamManager:
    def __init__(self, *, subjects=None, missing_reads=0, create_race=False):
        self.info = SimpleNamespace(config=FakeStreamConfig(subjects or []))
        self.missing_reads = missing_reads
        self.create_race = create_race
        self.added = []
        self.updated = []

    async def stream_info(self, name):
        assert name == STREAM_NAME
        if self.missing_reads:
            self.missing_reads -= 1
            raise NotFoundError
        return self.info

    async def add_stream(self, **config):
        self.added.append(config)
        if self.create_race:
            raise APIError(code=400, err_code=10058, description="stream exists")
        self.info = SimpleNamespace(
            config=FakeStreamConfig(config["subjects"]),
        )
        return self.info

    async def update_stream(self, *, config):
        self.updated.append(config)
        self.info = SimpleNamespace(config=config)
        return self.info


def _command():
    context = CorrelationContextV1.from_dict(
        {
            "tenant_id": "private",
            "operation_id": "operation-01",
            "contract_id": "operation-01",
            "correlation_id": "correlation-01",
            "causation_id": "causation-01",
            "execution_id": "execution-01",
            "actor_id": "operator:test",
            "request_id": "request-01",
            "trace_id": "trace-01",
            "service_name": "ultradex-api",
            "service_version": "2.0.0",
            "deployment_sha": "a" * 40,
            "environment": "test",
            "contract_version": "jobsearch.v1",
            "schema_version": "control-surface.v1",
        }
    )
    return JobSearchCommandV1.from_dict(
        {
            "command_id": "command-01",
            "command": "evidence.export",
            "actor_id": "operator:test",
            "idempotency_key": "export-01",
            "context": context.to_dict(),
            "parameters": {
                "subject_type": "opportunity",
                "subject_id": "opportunity-01",
                "profile": "accountability.v1",
            },
        }
    )


def test_command_subject_registry_is_closed_and_bounded():
    # COMMAND_SUBJECTS is derived from that shared catalog, so this bound tracks it.
    assert len(COMMAND_SUBJECTS) == len(COMMAND_NAMES_V1)
    assert COMMAND_SUBJECTS["sources.ingest"] == (
        "ultradex.jobsearch.commands.v1.sources-ingest"
    )
    assert COMMAND_SUBJECTS["intent.set"] == (
        "ultradex.jobsearch.commands.v1.intent-set"
    )
    assert COMMAND_SUBJECTS["outreach.send"].endswith(".outreach-send")
    assert lifecycle_subject("jobsearch.outreach.sent.v1") == (
        "ultradex.jobsearch.events.v1.jobsearch-outreach-sent-v1"
    )
    with pytest.raises(ValueError, match="event type"):
        lifecycle_subject("arbitrary token with spaces")


@pytest.mark.asyncio
async def test_jetstream_publisher_uses_canonical_payload_and_dedup_header():
    js = FakeJetStream()
    publisher = JobSearchNATSPublisher(
        url="nats://test",
        jetstream=js,
    )
    command = _command()

    await publisher.publish_command(command)

    subject, payload, headers = js.published[0]
    assert subject == COMMAND_SUBJECTS["evidence.export"]
    assert json.loads(payload) == command.to_dict()
    assert headers == {"Nats-Msg-Id": "export-01"}


@pytest.mark.asyncio
async def test_stream_setup_reconciles_missing_required_subjects():
    manager = FakeStreamManager(subjects=[f"{EVENT_SUBJECT_PREFIX}.*"])

    await ensure_jobsearch_stream(manager)

    assert manager.added == []
    assert len(manager.updated) == 1
    assert set(manager.updated[0].subjects) == set(REQUIRED_STREAM_SUBJECTS)


@pytest.mark.asyncio
async def test_stream_setup_tolerates_a_concurrent_create_race():
    manager = FakeStreamManager(
        subjects=list(REQUIRED_STREAM_SUBJECTS),
        missing_reads=1,
        create_race=True,
    )

    await ensure_jobsearch_stream(manager)

    assert len(manager.added) == 1
    assert manager.updated == []


@pytest.mark.asyncio
async def test_stream_setup_preserves_a_non_race_create_failure():
    manager = FakeStreamManager(
        missing_reads=2,
        create_race=True,
    )

    with pytest.raises(APIError, match="stream exists"):
        await ensure_jobsearch_stream(manager)
