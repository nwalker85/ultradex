from __future__ import annotations

import httpx
import pytest

from api.main import app
from api.dependencies import get_redis
from core import OperationEventDB, get_db
from tests.conftest import FakeRedis


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/contacts", "GET"),
        ("/api/v1/operations", "GET"),
        ("/api/v2/operations", "GET"),
        ("/api/v2/contacts/commands/sync", "POST"),
        ("/api/v2/delegations", "GET"),
    ],
)
async def test_private_rest_surfaces_require_auth(db_session, path, method):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.request(method, path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_graphql_missing_or_bad_bearer_returns_401(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            missing = await client.post("/api/graphql", json={"query": "{ __typename }"})
            bad = await client.post(
                "/api/graphql",
                json={"query": "{ __typename }"},
                headers={"Authorization": "Bearer wrong"},
            )
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_read_token_cannot_submit_commands(db_session, monkeypatch):
    monkeypatch.setenv("ULTRADEX_READ_TOKEN", "read-only-token")
    monkeypatch.setenv("ULTRADEX_READ_ID", "reader:agent")

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v2/contacts/commands/sync",
                headers={"Authorization": "Bearer read-only-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_spoofed_actor_header_cannot_change_authenticated_actor(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: FakeRedis()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer test-api-key"},
        ) as client:
            response = await client.post(
                "/api/v2/contacts/commands/sync",
                headers={"X-Actor-Id": "attacker:spoof"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    operation_id = response.json()["operation_id"]
    accepted = (
        db_session.query(OperationEventDB)
        .filter_by(operation_id=operation_id, event_type="operation.accepted")
        .one()
    )
    assert accepted.payload["actor_id"] == "operator:test"
    assert "attacker:spoof" not in str(accepted.payload)
