from __future__ import annotations

import json

import httpx
import pytest
from ravenhelm_contracts import ContractHandleV1

from sdk import UltradexClient


def _handle(operation_id="operation-01"):
    return {
        "contract_id": operation_id,
        "operation_id": operation_id,
        "status": "accepted",
        "submitted_at": "2026-07-23T14:00:00Z",
        "correlation_id": "correlation-01",
        "status_url": f"/api/v2/operations/{operation_id}",
        "events_url": f"/api/v1/operations/{operation_id}/events",
    }


@pytest.mark.asyncio
async def test_generic_sdk_command_sends_parameters_only_and_governance_headers():
    seen = []

    async def handler(request):
        seen.append(request)
        return httpx.Response(202, json=_handle())

    client = UltradexClient(
        api_url="https://ultradex.test",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )
    handle = await client.submit_jobsearch_command(
        "opportunities.create",
        {
            "employer": "Example",
            "title": "Platform Engineer",
            "source_evidence_id": "evidence-01",
        },
        idempotency_key="create-01",
        delegation_id="delegation-01",
        correlation_id="correlation-01",
    )
    await client.close()

    assert isinstance(handle, ContractHandleV1)
    assert seen[0].url.path == (
        "/api/v2/job-search/commands/opportunities.create"
    )
    assert json.loads(seen[0].content) == {
        "employer": "Example",
        "title": "Platform Engineer",
        "source_evidence_id": "evidence-01",
    }
    assert seen[0].headers["Idempotency-Key"] == "create-01"
    assert seen[0].headers["X-Delegation-Id"] == "delegation-01"
    assert seen[0].headers["X-Correlation-Id"] == "correlation-01"
    assert "X-Actor-Id" not in seen[0].headers


@pytest.mark.asyncio
async def test_sdk_rejects_invalid_contract_before_network_io():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(202, json=_handle())

    client = UltradexClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="approval_contract_id"):
        await client.submit_jobsearch_command(
            "outreach.send",
            {
                "outreach_id": "outreach-01",
                "message_commitment": f"sha256:{'a' * 64}",
                "channel": "gmail",
            },
            idempotency_key="invalid-send",
        )
    await client.close()
    assert calls == 0


@pytest.mark.asyncio
async def test_sdk_exposes_one_convenience_method_per_canonical_command():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            202,
            json=_handle(f"operation-{len(requests)}"),
        )

    client = UltradexClient(transport=httpx.MockTransport(handler))
    await client.submit_sources_ingest(
        source_kind="web",
        source_ref="web-source-01",
        observed_at="2026-07-23T14:00:00Z",
        idempotency_key="1",
    )
    await client.submit_opportunity_create(
        employer="Example",
        title="Platform Engineer",
        source_evidence_id="evidence-01",
        idempotency_key="2",
    )
    await client.submit_opportunity_score(
        opportunity_id="opportunity-01",
        lens="executive",
        idempotency_key="3",
    )
    await client.submit_application_transition(
        application_id="application-01",
        status="applied",
        occurred_at="2026-07-23T14:00:00Z",
        idempotency_key="4",
    )
    await client.submit_relationship_sync(
        opportunity_id="opportunity-01",
        dex_contact_ref="dex-contact-01",
        idempotency_key="5",
    )
    await client.submit_outreach_prepare(
        opportunity_id="opportunity-01",
        channel="gmail",
        message_commitment=f"sha256:{'a' * 64}",
        idempotency_key="6",
    )
    await client.submit_outreach_approve(
        outreach_id="outreach-01",
        message_commitment=f"sha256:{'a' * 64}",
        idempotency_key="7",
    )
    await client.submit_outreach_send(
        outreach_id="outreach-01",
        approval_contract_id="approval-01",
        message_commitment=f"sha256:{'a' * 64}",
        channel="gmail",
        idempotency_key="8",
    )
    await client.submit_evidence_export(
        subject_type="opportunity",
        subject_id="opportunity-01",
        profile="accountability.v1",
        idempotency_key="9",
    )
    await client.close()

    assert [request.url.path.rsplit("/", 1)[-1] for request in requests] == [
        "sources.ingest",
        "opportunities.create",
        "opportunities.score",
        "applications.transition",
        "relationships.sync",
        "outreach.prepare",
        "outreach.approve",
        "outreach.send",
        "evidence.export",
    ]
