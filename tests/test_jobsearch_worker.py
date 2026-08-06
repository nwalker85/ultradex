from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.jobsearch_commands import JobSearchCommandRequest, JobSearchGatewayService
from core.jobsearch_executors import (
    EvidenceIngestResult,
    JobSearchExecutor,
    RetryableCommandError,
)
from core.jobsearch_worker import JobSearchWorker


COMMITMENT = f"sha256:{'a' * 64}"


class Message:
    def __init__(self, payload, attempt=1):
        self.data = payload
        self.metadata = SimpleNamespace(num_delivered=attempt)
        self.acked = 0
        self.termed = 0
        self.naks = []

    async def ack(self):
        self.acked += 1

    async def term(self):
        self.termed += 1

    async def nak(self, delay=None):
        self.naks.append(delay)


class Source:
    async def ingest(self, command):
        return EvidenceIngestResult(
            evidence_id="evidence-worker-01",
            source_kind="web",
            source_ref="web-source-01",
            observed_at="2026-07-23T14:00:00Z",
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
        )


class RetrySource:
    async def ingest(self, command):
        raise RetryableCommandError("source_timeout")


async def _command(db, publisher, issuer, key):
    await JobSearchGatewayService(publisher, issuer).submit_command(
        db,
        JobSearchCommandRequest(
            command="sources.ingest",
            parameters={
                "source_kind": "web",
                "source_ref": "web-source-01",
                "observed_at": "2026-07-23T14:00:00Z",
            },
            actor_id="operator:test",
            idempotency_key=key,
        ),
    )
    return publisher.commands[-1]


@pytest.mark.asyncio
async def test_worker_terms_malformed_or_unregistered_task(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    worker = JobSearchWorker(
        JobSearchExecutor(db_session, receipt_issuer),
        fake_jobsearch_publisher,
    )
    malformed = Message(b"{not-json")
    unregistered = Message(
        json.dumps(
            {
                "command_id": "command-01",
                "command": "shell.exec",
            }
        ).encode()
    )

    await worker.handle_message(malformed)
    await worker.handle_message(unregistered)

    assert malformed.termed == 1
    assert unregistered.termed == 1
    assert malformed.acked == unregistered.acked == 0


@pytest.mark.asyncio
async def test_worker_acks_only_after_terminal_event_publication(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _command(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "worker-success",
    )
    worker = JobSearchWorker(
        JobSearchExecutor(
            db_session,
            receipt_issuer,
            source_adapter=Source(),
        ),
        fake_jobsearch_publisher,
    )
    message = Message(
        json.dumps(command.to_dict()).encode(),
        attempt=1,
    )

    await worker.handle_message(message)

    assert message.acked == 1
    assert message.termed == 0
    assert message.naks == []
    assert fake_jobsearch_publisher.events[-1].control_surface_event.lifecycle_state == (
        "succeeded"
    )


@pytest.mark.asyncio
async def test_worker_delays_retryable_failure_and_acks_final_failure(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _command(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "worker-retry",
    )
    worker = JobSearchWorker(
        JobSearchExecutor(
            db_session,
            receipt_issuer,
            source_adapter=RetrySource(),
            max_attempts=3,
        ),
        fake_jobsearch_publisher,
        retry_delay_seconds=5,
    )
    first = Message(json.dumps(command.to_dict()).encode(), attempt=1)
    final = Message(json.dumps(command.to_dict()).encode(), attempt=3)

    await worker.handle_message(first)
    await worker.handle_message(final)

    assert first.naks == [5]
    assert first.acked == 0
    assert final.acked == 1
    assert fake_jobsearch_publisher.events[-1].control_surface_event.lifecycle_state == (
        "failed"
    )
