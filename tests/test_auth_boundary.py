from __future__ import annotations

import httpx
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import authenticate_principal, validate_auth_configuration
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
        ("/api/v2/job-search/commands/evidence.export", "POST"),
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


@pytest.mark.parametrize(
    ("token", "subject", "expected_scopes"),
    [
        (
            "full-operator-token",
            "operator:fixture",
            frozenset({"read", "command", "delegation-admin"}),
        ),
        (
            "command-only-token",
            "career-operator:fixture",
            frozenset({"read", "command"}),
        ),
        (
            "read-only-token",
            "reader:fixture",
            frozenset({"read"}),
        ),
    ],
)
def test_distinct_coexisting_credentials_retain_exact_scopes(
    monkeypatch,
    token,
    subject,
    expected_scopes,
):
    monkeypatch.setenv("ULTRADEX_API_TOKEN", "full-operator-token")
    monkeypatch.setenv("ULTRADEX_OPERATOR_ID", "operator:fixture")
    monkeypatch.setenv("ULTRADEX_COMMAND_TOKEN", "command-only-token")
    monkeypatch.setenv("ULTRADEX_COMMAND_ID", "career-operator:fixture")
    monkeypatch.setenv("ULTRADEX_READ_TOKEN", "read-only-token")
    monkeypatch.setenv("ULTRADEX_READ_ID", "reader:fixture")

    principal = authenticate_principal(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert principal.subject == subject
    assert principal.scopes == expected_scopes


def test_absent_command_pair_preserves_legacy_operator_precedence_for_equal_tokens(
    monkeypatch,
):
    monkeypatch.setenv("ULTRADEX_API_TOKEN", "legacy-shared-token")
    monkeypatch.setenv("ULTRADEX_OPERATOR_ID", "operator:fixture")
    monkeypatch.setenv("ULTRADEX_READ_TOKEN", "legacy-shared-token")
    monkeypatch.setenv("ULTRADEX_READ_ID", "reader:fixture")
    monkeypatch.delenv("ULTRADEX_COMMAND_TOKEN", raising=False)
    monkeypatch.delenv("ULTRADEX_COMMAND_ID", raising=False)

    validate_auth_configuration()
    principal = authenticate_principal(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="legacy-shared-token",
        )
    )

    assert principal.subject == "operator:fixture"
    assert principal.scopes == frozenset({"read", "command", "delegation-admin"})


def test_command_credential_has_exactly_read_and_command_scopes(monkeypatch):
    monkeypatch.setenv("ULTRADEX_COMMAND_TOKEN", "command-only-token")
    monkeypatch.setenv("ULTRADEX_COMMAND_ID", "career-operator:fixture")

    principal = authenticate_principal(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="command-only-token",
        )
    )

    assert principal.subject == "career-operator:fixture"
    assert principal.scopes == frozenset({"read", "command"})


@pytest.mark.asyncio
async def test_command_credential_cannot_access_delegation_administration(
    monkeypatch,
):
    monkeypatch.setenv("ULTRADEX_COMMAND_TOKEN", "command-only-token")
    monkeypatch.setenv("ULTRADEX_COMMAND_ID", "career-operator:fixture")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v2/delegations",
            headers={"Authorization": "Bearer command-only-token"},
        )

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
