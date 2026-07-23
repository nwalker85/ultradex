from __future__ import annotations

import json

import pytest
from ravenhelm_contracts import CorrelationContextV1, JobSearchCommandV1

from core.jobsearch_nats import (
    COMMAND_SUBJECTS,
    JobSearchNATSPublisher,
    lifecycle_subject,
)


class FakeJetStream:
    def __init__(self):
        self.published = []

    async def publish(self, subject, payload, headers=None):
        self.published.append((subject, payload, headers))


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
    assert len(COMMAND_SUBJECTS) == 9
    assert COMMAND_SUBJECTS["sources.ingest"] == (
        "ultradex.jobsearch.commands.v1.sources-ingest"
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
