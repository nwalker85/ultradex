from __future__ import annotations

import json

import httpx
import pytest
from ravenhelm_contracts import (
    CONTROL_SURFACE_V1_SCHEMA_PATHS,
    ContractHandleV1,
)

from api.dependencies import get_jobsearch_publisher, get_receipt_issuer
from api.main import app
from core import JobSearchCommandDB, OperationDB, get_db
from tests.conftest import FakeJobSearchPublisher


VALID_COMMANDS = {
    "sources.ingest": {
        "source_kind": "web",
        "source_ref": "web-source-01",
        "observed_at": "2026-07-23T14:00:00Z",
    },
    "opportunities.create": {
        "employer": "Example",
        "title": "Platform Engineer",
        "source_evidence_id": "evidence-01",
    },
    "opportunities.score": {
        "opportunity_id": "opportunity-01",
        "lens": "executive",
    },
    "applications.transition": {
        "application_id": "application-01",
        "status": "applied",
        "occurred_at": "2026-07-23T14:00:00Z",
    },
    "relationships.sync": {
        "opportunity_id": "opportunity-01",
        "dex_contact_ref": "dex-contact-01",
    },
    "outreach.prepare": {
        "opportunity_id": "opportunity-01",
        "channel": "gmail",
        "message_commitment": f"sha256:{'a' * 64}",
    },
    "outreach.approve": {
        "outreach_id": "outreach-01",
        "message_commitment": f"sha256:{'a' * 64}",
    },
    "outreach.send": {
        "outreach_id": "outreach-01",
        "approval_contract_id": "approval-01",
        "message_commitment": f"sha256:{'a' * 64}",
        "channel": "gmail",
    },
    "evidence.export": {
        "subject_type": "opportunity",
        "subject_id": "opportunity-01",
        "profile": "accountability.v1",
    },
}


@pytest.fixture
async def command_api(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_jobsearch_publisher] = (
        lambda: fake_jobsearch_publisher
    )
    app.dependency_overrides[get_receipt_issuer] = lambda: receipt_issuer
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-api-key"},
    ) as client:
        yield client, fake_jobsearch_publisher, db_session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(("command_name", "parameters"), VALID_COMMANDS.items())
async def test_all_canonical_commands_return_shared_accepted_handle(
    command_api,
    command_name,
    parameters,
):
    client, publisher, db = command_api
    response = await client.post(
        f"/api/v2/job-search/commands/{command_name}",
        json=parameters,
        headers={
            "Idempotency-Key": f"key-{command_name}",
            "X-Actor-Id": "attacker:spoof",
            "X-Correlation-Id": f"correlation-{command_name}",
        },
    )

    assert response.status_code == 202
    handle = ContractHandleV1.from_dict(response.json())
    assert handle.status == "accepted"
    row = db.get(JobSearchCommandDB, handle.operation_id)
    assert row.actor_id == "operator:test"
    assert "attacker:spoof" not in str(row.context)
    assert row.context["correlation_id"] == f"correlation-{command_name}"
    assert publisher.commands[-1].command == command_name


@pytest.mark.asyncio
async def test_api_replay_conflict_and_validation_boundaries(command_api):
    client, publisher, db = command_api
    headers = {"Idempotency-Key": "create-01"}
    first = await client.post(
        "/api/v2/job-search/commands/opportunities.create",
        json=VALID_COMMANDS["opportunities.create"],
        headers=headers,
    )
    replay = await client.post(
        "/api/v2/job-search/commands/opportunities.create",
        json=VALID_COMMANDS["opportunities.create"],
        headers=headers,
    )
    conflict = await client.post(
        "/api/v2/job-search/commands/opportunities.create",
        json={
            **VALID_COMMANDS["opportunities.create"],
            "title": "Different",
        },
        headers=headers,
    )
    invalid = await client.post(
        "/api/v2/job-search/commands/outreach.send",
        json={
            "outreach_id": "outreach-01",
            "message_commitment": f"sha256:{'a' * 64}",
            "channel": "gmail",
        },
        headers={"Idempotency-Key": "invalid-send"},
    )
    unknown = await client.post(
        "/api/v2/job-search/commands/shell.exec",
        json={},
        headers={"Idempotency-Key": "unknown"},
    )
    missing_key = await client.post(
        "/api/v2/job-search/commands/evidence.export",
        json=VALID_COMMANDS["evidence.export"],
    )

    first_handle = ContractHandleV1.from_dict(first.json())
    replay_handle = ContractHandleV1.from_dict(replay.json())
    assert replay_handle.operation_id == first_handle.operation_id
    assert conflict.status_code == 409
    assert invalid.status_code == 422
    assert unknown.status_code == 422
    assert missing_key.status_code == 422
    assert db.query(OperationDB).count() == 1
    assert len(publisher.commands) == 1


@pytest.mark.asyncio
async def test_unavailable_nats_returns_governed_failed_handle(
    db_session,
    receipt_issuer,
):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_jobsearch_publisher] = lambda: (
        FakeJobSearchPublisher(fail_commands=True)
    )
    app.dependency_overrides[get_receipt_issuer] = lambda: receipt_issuer
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer test-api-key"},
        ) as client:
            response = await client.post(
                "/api/v2/job-search/commands/opportunities.create",
                json=VALID_COMMANDS["opportunities.create"],
                headers={"Idempotency-Key": "nats-down"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    handle = ContractHandleV1.from_dict(response.json())
    assert handle.status == "failed"


def test_jobsearch_openapi_projects_exact_shared_handle_schema():
    response_schema = app.openapi()["paths"][
        "/api/v2/job-search/commands/{command_name}"
    ]["post"]["responses"]["202"]["content"]["application/json"]["schema"]
    failure_schema = app.openapi()["paths"][
        "/api/v2/job-search/commands/{command_name}"
    ]["post"]["responses"]["503"]["content"]["application/json"]["schema"]
    shared = json.loads(
        CONTROL_SURFACE_V1_SCHEMA_PATHS["contract_handle"].read_text()
    )
    assert response_schema == shared
    assert failure_schema == shared
