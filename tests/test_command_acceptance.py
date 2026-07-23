from __future__ import annotations

from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import httpx
import pytest
from ravenhelm_contracts import CONTROL_SURFACE_V1_SCHEMA_PATHS, ContractHandleV1

from api.dependencies import get_redis
from api.main import app
from api.routes.v2.commands import _accepted_handle
from core import get_db, IdempotencyKeyDB, OperationEventDB
from tests.conftest import FailingRedis


@pytest.fixture
async def api_client(db_session, fake_redis):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-api-key"},
    ) as client:
        yield client, fake_redis, db_session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analyze_accepts_json_and_returns_shared_contract_handle(api_client):
    client, redis, db = api_client
    response = await client.post(
        "/api/v2/contacts/commands/analyze",
        json={"limit": 5},
        headers={
            "Idempotency-Key": "analyze-5",
            "X-Correlation-Id": "corr-analyze-5",
        },
    )

    assert response.status_code == 202
    handle = ContractHandleV1.from_dict(response.json())
    assert handle.status == "accepted"
    assert handle.correlation_id == "corr-analyze-5"
    assert handle.contract_id == handle.operation_id
    assert handle.status_url == f"/api/v2/operations/{handle.operation_id}"
    assert handle.events_url == f"/api/v1/operations/{handle.operation_id}/events"
    assert redis.enqueued == [("analyze_task", (handle.operation_id, {"limit": 5}))]
    event = db.query(OperationEventDB).filter_by(operation_id=handle.operation_id).one()
    assert event.payload["actor_id"] == "operator:test"

    repeated = await client.post(
        "/api/v2/contacts/commands/analyze",
        json={"limit": 5},
        headers={"Idempotency-Key": "analyze-5"},
    )
    repeated_handle = ContractHandleV1.from_dict(repeated.json())
    assert repeated_handle.operation_id == handle.operation_id
    assert len(redis.enqueued) == 1


@pytest.mark.asyncio
async def test_analyze_preserves_legacy_query_limit(api_client):
    client, redis, _ = api_client
    response = await client.post("/api/v2/contacts/commands/analyze?limit=3")

    handle = ContractHandleV1.from_dict(response.json())
    assert response.status_code == 202
    assert redis.enqueued == [("analyze_task", (handle.operation_id, {"limit": 3}))]


@pytest.mark.asyncio
async def test_sync_returns_an_accepted_handle(api_client):
    client, redis, _ = api_client
    response = await client.post(
        "/api/v2/contacts/commands/sync",
        headers={"Idempotency-Key": "sync-1"},
    )

    handle = ContractHandleV1.from_dict(response.json())
    assert response.status_code == 202
    assert handle.status == "accepted"
    assert redis.enqueued == [("sync_task", (handle.operation_id, {}))]


def test_openapi_projects_the_shared_contract_handle_schema():
    response_schema = app.openapi()["paths"][
        "/api/v2/contacts/commands/analyze"
    ]["post"]["responses"]["202"]["content"]["application/json"]["schema"]

    shared_schema = json.loads(
        CONTROL_SURFACE_V1_SCHEMA_PATHS["contract_handle"].read_text()
    )
    assert response_schema == shared_schema
    failed_schema = app.openapi()["paths"][
        "/api/v2/contacts/commands/analyze"
    ]["post"]["responses"]["503"]["content"]["application/json"]["schema"]
    assert failed_schema == shared_schema


def test_contract_handle_helper_enforces_the_shared_runtime_validator():
    invalid = SimpleNamespace(
        id="",
        correlation_id="corr-invalid",
        created_at=datetime(2026, 7, 22, 12, 0, 0),
        status="pending",
    )

    with pytest.raises(ValueError, match="contract_id"):
        _accepted_handle(invalid)


def test_legacy_naive_submission_time_preserves_the_original_instant():
    created_at = datetime(2026, 7, 22, 12, 0, 0)
    operation = SimpleNamespace(
        id="op-time",
        correlation_id="corr-time",
        created_at=created_at,
        status="pending",
    )

    handle = ContractHandleV1.from_dict(_accepted_handle(operation))
    submitted_at = datetime.fromisoformat(handle.submitted_at)

    assert submitted_at.timestamp() == created_at.timestamp()


@pytest.mark.asyncio
async def test_idempotency_key_is_bound_to_actor_command_and_parameters(api_client):
    client, redis, _ = api_client
    headers = {
        "Authorization": "Bearer test-api-key",
        "Idempotency-Key": "bounded-key",
        "X-Actor-Id": "operator:nate",
    }
    first = await client.post(
        "/api/v2/contacts/commands/analyze",
        json={"limit": 5},
        headers=headers,
    )
    assert first.status_code == 202

    conflicting = await client.post(
        "/api/v2/contacts/commands/analyze",
        json={"limit": 6},
        headers=headers,
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"]["code"] == "idempotency_conflict"
    assert len(redis.enqueued) == 1


@pytest.mark.asyncio
async def test_expired_idempotency_key_is_atomically_replaced(api_client):
    client, redis, db = api_client
    db.add(
        IdempotencyKeyDB(
            key="expired-key",
            operation_id="old-operation",
            expires_at=datetime.now() - timedelta(seconds=1),
        )
    )
    db.commit()

    response = await client.post(
        "/api/v2/contacts/commands/sync",
        headers={"Idempotency-Key": "expired-key"},
    )

    assert response.status_code == 202
    handle = ContractHandleV1.from_dict(response.json())
    binding = db.get(IdempotencyKeyDB, "expired-key")
    assert binding.operation_id == handle.operation_id
    assert binding.operation_id != "old-operation"
    assert len(redis.enqueued) == 1


@pytest.mark.asyncio
async def test_queue_failure_returns_a_failed_contract_handle_and_stays_failed(
    db_session,
):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: FailingRedis()
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Authorization": "Bearer test-api-key",
        "Idempotency-Key": "queue-failure",
        "X-Actor-Id": "operator:nate",
    }
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/api/v2/contacts/commands/sync",
                headers=headers,
            )
            repeated = await client.post(
                "/api/v2/contacts/commands/sync",
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 503
    assert repeated.status_code == 503
    first_handle = ContractHandleV1.from_dict(first.json())
    repeated_handle = ContractHandleV1.from_dict(repeated.json())
    assert first_handle.status == "failed"
    assert repeated_handle.status == "failed"
    assert repeated_handle.operation_id == first_handle.operation_id
    event_types = [
        row.event_type
        for row in db_session.query(OperationEventDB)
        .filter_by(operation_id=first_handle.operation_id)
        .order_by(OperationEventDB.id)
        .all()
    ]
    assert event_types == ["operation.accepted", "task.failed"]
