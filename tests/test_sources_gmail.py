"""Sense #2 — Gmail adapter. Metadata-only: thread IDs, never subjects."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ravenhelm_contracts.control_surface_v1 import CorrelationContextV1
from ravenhelm_contracts.jobsearch_v1 import (
    DIGEST_PATTERN_V1,
    OPAQUE_REFERENCE_PATTERN_V1,
    JobSearchCommandV1,
)

from core.jobsearch_executors import DomainRefusal
import httpx

from core.jobsearch_gmail import (
    DEFAULT_GMAIL_SENSE_QUERY,
    GmailAuthError,
    GmailSourceAdapter,
    GmailSweep,
    normalize_thread_ids,
    refresh_access_token,
    resolve_access_token,
)
from core.jobsearch_sources import RoutedSourceAdapter


NOW = datetime(2026, 8, 22, 7, 0, 0, tzinfo=timezone.utc)


def _command(declaration) -> JobSearchCommandV1:
    ctx = CorrelationContextV1(
        tenant_id="tenant:test", operation_id="op:1", contract_id="contract:1",
        correlation_id="corr:1", causation_id="cause:1", execution_id="exec:1",
        actor_id="operator:test", request_id="req:1", trace_id="trace:1",
        service_name="ultradex-test", service_version="0.0.0-test",
        deployment_sha="testsha", environment="test",
        contract_version="1.0.0", schema_version="1.0.0",
    )
    return JobSearchCommandV1(
        command_id="cmd:1", command="sources.ingest", actor_id="operator:test",
        idempotency_key="idem:1", context=ctx,
        parameters={
            "source_kind": declaration.source_kind,
            "source_ref": declaration.source_ref,
            "observed_at": declaration.observed_at,
        },
    )


class TestNormalize:
    def test_dedupes_and_sorts(self):
        assert normalize_thread_ids(["b", " a ", "b", ""]) == ["a", "b"]


class TestSweep:
    def _run(self, ids=("thread-aaa", "thread-bbb")):
        stash: dict[str, dict] = {}
        declaration = GmailSweep(stash=stash, now=lambda: NOW).run(
            ids, query=DEFAULT_GMAIL_SENSE_QUERY,
        )
        return declaration, stash

    def test_declaration_conforms(self):
        declaration, _ = self._run()
        assert declaration is not None
        assert declaration.source_kind == "gmail"
        assert OPAQUE_REFERENCE_PATTERN_V1.match(declaration.source_ref)
        assert DIGEST_PATTERN_V1.match(declaration.commitment)
        assert declaration.observed_at == "2026-08-22T07:00:00Z"
        assert declaration.redacted_summary == "gmail sweep: 2 threads"

    def test_redacted_summary_has_no_thread_ids(self):
        declaration, _ = self._run()
        assert declaration is not None
        assert "thread-aaa" not in declaration.redacted_summary

    def test_identical_inputs_are_idempotent(self):
        d1, _ = self._run()
        d2, _ = self._run()
        assert d1.source_ref == d2.source_ref
        assert d1.commitment == d2.commitment

    def test_empty_declares_nothing_by_default(self):
        sweep = GmailSweep(stash={}, now=lambda: NOW)
        assert sweep.run([], query=DEFAULT_GMAIL_SENSE_QUERY) is None


class TestAdapter:
    @pytest.mark.asyncio
    async def test_proves_stashed_claim(self):
        stash: dict[str, dict] = {}
        declaration = GmailSweep(stash=stash, now=lambda: NOW).run(
            ["thread-aaa"], query=DEFAULT_GMAIL_SENSE_QUERY,
        )
        assert declaration is not None
        result = await GmailSourceAdapter(stash=stash).ingest(_command(declaration))
        assert result.source_kind == "gmail"
        assert result.source_ref == declaration.source_ref
        assert result.evidence_id.startswith("evidence-gmail-")

    @pytest.mark.asyncio
    async def test_refuses_unproven_claim(self):
        declaration_like = type("D", (), {
            "source_kind": "gmail",
            "source_ref": "gmail-sweep:20260822:aaaaaaaaaaaa",
            "observed_at": "2026-08-22T07:00:00Z",
        })()
        with pytest.raises(DomainRefusal):
            await GmailSourceAdapter(stash={}).ingest(_command(declaration_like))

    @pytest.mark.asyncio
    async def test_router_sends_gmail_to_gmail_adapter(self):
        stash: dict[str, dict] = {}
        declaration = GmailSweep(stash=stash, now=lambda: NOW).run(
            ["thread-aaa"], query=DEFAULT_GMAIL_SENSE_QUERY,
        )
        assert declaration is not None
        router = RoutedSourceAdapter({"gmail": GmailSourceAdapter(stash=stash)})
        result = await router.ingest(_command(declaration))
        assert result.source_kind == "gmail"

    @pytest.mark.asyncio
    async def test_router_unbound_kind_refuses(self):
        declaration_like = type("D", (), {
            "source_kind": "linkedin",
            "source_ref": "linkedin-sweep:20260822:aaaaaaaaaaaa",
            "observed_at": "2026-08-22T07:00:00Z",
        })()
        router = RoutedSourceAdapter({})
        with pytest.raises(DomainRefusal) as raised:
            await router.ingest(_command(declaration_like))
        assert raised.value.reason_code == "source_adapter_unbound"


class TestRefreshAccessToken:
    def test_exchanges_refresh_token_for_access_token(self):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                200,
                json={"access_token": "ya29.test-access", "expires_in": 3600},
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        token = refresh_access_token(
            client_id="cid",
            client_secret="csecret",
            refresh_token="1//test-refresh",
            client=client,
        )
        assert token == "ya29.test-access"
        assert len(seen) == 1
        assert str(seen[0].url) == "https://oauth2.googleapis.com/token"
        body = seen[0].content.decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=1%2F%2Ftest-refresh" in body

    def test_invalid_grant_is_a_reason_code(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "invalid_grant"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with pytest.raises(GmailAuthError) as raised:
            refresh_access_token(
                client_id="cid",
                client_secret="csecret",
                refresh_token="expired",
                client=client,
            )
        assert raised.value.reason_code == "gmail_refresh_invalid_grant"


class TestResolveAccessToken:
    def test_prefers_direct_access_token(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        token = resolve_access_token(
            environ={"GMAIL_ACCESS_TOKEN": "ya29.direct"},
            client=client,
        )
        assert token == "ya29.direct"

    def test_refreshes_when_access_token_absent(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"access_token": "ya29.from-refresh"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        token = resolve_access_token(
            environ={
                "GMAIL_CLIENT_ID": "cid",
                "GMAIL_CLIENT_SECRET": "csecret",
                "GMAIL_REFRESH_TOKEN": "1//refresh",
            },
            client=client,
        )
        assert token == "ya29.from-refresh"

    def test_missing_credentials_refuse(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        with pytest.raises(GmailAuthError) as raised:
            resolve_access_token(environ={}, client=client)
        assert raised.value.reason_code == "gmail_credentials_missing"
