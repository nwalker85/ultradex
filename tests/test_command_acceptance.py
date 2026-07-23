from __future__ import annotations

import httpx
import pytest
from ravenhelm_contracts import ContractHandleV1

from api.dependencies import get_redis
from api.main import app
from core import get_db, OperationEventDB


@pytest.fixture
async def api_client(db_session, fake_redis):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
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
            "X-Actor-Id": "operator:nate",
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
    assert event.payload["actor_id"] == "operator:nate"

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

    assert set(response_schema["required"]) == {
        "contract_id",
        "operation_id",
        "status",
        "submitted_at",
        "correlation_id",
    }
    assert response_schema["properties"]["contract_id"]["type"] == "string"
