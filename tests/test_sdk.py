from __future__ import annotations

import json

import httpx
import pytest
from ravenhelm_contracts import ContractHandleV1

from sdk import UltradexClient


def accepted_handle(operation_id: str = "op-1") -> dict[str, str]:
    return {
        "contract_id": operation_id,
        "operation_id": operation_id,
        "status": "accepted",
        "submitted_at": "2026-07-22T12:00:00+00:00",
        "correlation_id": "corr-1",
        "status_url": f"/api/v2/operations/{operation_id}",
        "events_url": f"/api/v1/operations/{operation_id}/events",
    }


@pytest.mark.asyncio
async def test_submit_analyze_returns_typed_handle_and_preserves_headers():
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, json=accepted_handle())

    client = UltradexClient(
        api_url="https://ultradex.test",
        api_key="api-secret",
        transport=httpx.MockTransport(handler),
    )
    handle = await client.submit_analyze_contacts(limit=8, idempotency_key="idem-8")
    await client.close()

    assert isinstance(handle, ContractHandleV1)
    assert json.loads(seen[0].content) == {"limit": 8}
    assert seen[0].headers["Authorization"] == "Bearer api-secret"
    assert seen[0].headers["Idempotency-Key"] == "idem-8"


@pytest.mark.asyncio
async def test_submit_returns_governed_failed_handle_from_queue_outage():
    failed = accepted_handle("op-failed")
    failed["status"] = "failed"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=failed)

    client = UltradexClient(transport=httpx.MockTransport(handler))
    handle = await client.submit_sync_contacts()
    await client.close()

    assert handle.status == "failed"
    assert handle.operation_id == "op-failed"


@pytest.mark.asyncio
async def test_submit_preserves_delegation_and_zero_limit():
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, json=accepted_handle())

    client = UltradexClient(transport=httpx.MockTransport(handler))
    await client.submit_analyze_contacts(limit=0, delegation_id="delegation:1")
    await client.close()

    assert json.loads(seen[0].content) == {"limit": 0}
    assert seen[0].headers["X-Delegation-Id"] == "delegation:1"


@pytest.mark.asyncio
async def test_submit_drops_spoofable_actor_and_preserves_correlation_header():
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = accepted_handle()
        payload["correlation_id"] = "corr-sdk"
        return httpx.Response(202, json=payload)

    client = UltradexClient(transport=httpx.MockTransport(handler))
    handle = await client.submit_sync_contacts(
        actor_id="operator:nate",
        correlation_id="corr-sdk",
    )
    await client.close()

    assert handle.correlation_id == "corr-sdk"
    assert "X-Actor-Id" not in seen[0].headers
    assert seen[0].headers["X-Correlation-Id"] == "corr-sdk"


@pytest.mark.asyncio
async def test_submit_rejects_malformed_server_handle():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"id": "legacy-only"})

    client = UltradexClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError):
        await client.submit_sync_contacts()
    await client.close()


@pytest.mark.asyncio
async def test_legacy_analyze_composes_submit_and_poll(monkeypatch):
    client = UltradexClient(transport=httpx.MockTransport(lambda request: None))
    handle = ContractHandleV1.from_dict(accepted_handle("op-legacy"))

    async def fake_submit(**kwargs):
        return handle

    async def fake_poll(operation_id: str, timeout: int):
        return {"id": operation_id, "status": "completed"}

    monkeypatch.setattr(client, "submit_analyze_contacts", fake_submit)
    monkeypatch.setattr(client, "_poll_operation", fake_poll)

    result = await client.analyze_contacts(limit=4, poll_timeout=9)
    await client.close()
    assert result == {"id": "op-legacy", "status": "completed"}


@pytest.mark.asyncio
async def test_operation_reads_use_graphql_projection_surface():
    seen: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if "events(" in payload["query"]:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "events": [
                            {
                                "id": 1,
                                "operation_id": "op-read",
                                "event_type": "operation.accepted",
                                "timestamp": "2026-07-22T12:00:00",
                                "payload": {},
                            }
                        ]
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "operation": {
                        "id": "op-read",
                        "status": "running",
                        "command": "analyze",
                        "correlation_id": "corr-read",
                        "created_at": "2026-07-22T12:00:00",
                        "started_at": None,
                        "completed_at": None,
                        "result": None,
                        "error": None,
                    }
                }
            },
        )

    client = UltradexClient(transport=httpx.MockTransport(handler))
    operation = await client.get_operation("op-read")
    events = await client.get_operation_events("op-read", first=25, after=10)
    await client.close()

    assert operation["id"] == "op-read"
    assert events[0]["event_type"] == "operation.accepted"
    assert seen[0]["variables"] == {"operationId": "op-read"}
    assert seen[1]["variables"] == {
        "operationId": "op-read",
        "first": 25,
        "after": 10,
    }


@pytest.mark.asyncio
async def test_poll_recognizes_control_surface_terminal_states(monkeypatch):
    client = UltradexClient(transport=httpx.MockTransport(lambda request: None))

    async def succeeded(operation_id: str):
        return {"id": operation_id, "status": "succeeded"}

    monkeypatch.setattr(client, "get_operation", succeeded)
    result = await client._poll_operation("op-terminal", timeout=1, poll_interval=0)
    await client.close()

    assert result["status"] == "succeeded"
