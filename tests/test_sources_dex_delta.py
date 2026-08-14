"""WP5 — Dex-delta Sense adapter (Sense #1).

The sweep runs first and stashes its payload; the command pre-declares
(source_kind, source_ref, observed_at); the adapter proves the claim by
retrieval. Commit-then-execute — the accountability shape, not a cron job.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from ravenhelm_contracts.control_surface_v1 import CorrelationContextV1
from ravenhelm_contracts.jobsearch_v1 import (
    DIGEST_PATTERN_V1,
    OPAQUE_REFERENCE_PATTERN_V1,
    JobSearchCommandV1,
)

from core.jobsearch_executors import DomainRefusal
from core.jobsearch_sources import (
    DexDeltaSourceAdapter,
    DexSweep,
    compute_dex_delta,
)
from core.models import ContactBase


def _contact(cid: str, name: str, email: str | None = None, last_contacted: datetime | None = None):
    return {
        "id": cid,
        "name": name,
        "email": email,
        "phone": None,
        "last_contacted": last_contacted,
    }


def _dex_contact(cid: str, name: str, email: str | None = None) -> ContactBase:
    return ContactBase(id=cid, name=name, email=email)


NOW = datetime(2026, 8, 14, 6, 0, 0, tzinfo=timezone.utc)


class TestDelta:
    def test_detects_new_changed_neglected(self):
        local = [
            _contact("c1", "Alice", "alice@x.com"),
            _contact("c2", "Bob", "bob@x.com", last_contacted=NOW - timedelta(days=200)),
        ]
        remote = [
            _dex_contact("c1", "Alice", "alice@NEW.com"),  # changed
            _dex_contact("c2", "Bob", "bob@x.com"),        # neglected (stale last_contacted)
            _dex_contact("c3", "Carol", "carol@x.com"),    # new
        ]
        delta = compute_dex_delta(remote, local, now=NOW, neglect_days=90)
        assert [c["id"] for c in delta["new"]] == ["c3"]
        assert [c["id"] for c in delta["changed"]] == ["c1"]
        assert [c["id"] for c in delta["neglected"]] == ["c2"]

    def test_no_drift_means_empty_delta(self):
        local = [_contact("c1", "Alice", "alice@x.com", last_contacted=NOW)]
        remote = [_dex_contact("c1", "Alice", "alice@x.com")]
        delta = compute_dex_delta(remote, local, now=NOW, neglect_days=90)
        assert delta["new"] == [] and delta["changed"] == [] and delta["neglected"] == []


class TestSweepDeclaration:
    def _sweep(self):
        local = [_contact("c1", "Alice", "alice@x.com")]
        remote = [
            _dex_contact("c1", "Alice", "alice@NEW.com"),
            _dex_contact("c3", "Carol", "carol@x.com"),
        ]
        stash: dict[str, dict] = {}
        sweep = DexSweep(stash=stash, now=lambda: NOW)
        declaration = sweep.run(remote, local, neglect_days=90)
        return declaration, stash

    def test_declaration_conforms_to_contract_patterns(self):
        declaration, _ = self._sweep()
        assert declaration.source_kind == "dex"
        assert OPAQUE_REFERENCE_PATTERN_V1.match(declaration.source_ref)
        assert DIGEST_PATTERN_V1.match(declaration.commitment)
        assert declaration.observed_at == "2026-08-14T06:00:00Z"

    def test_identical_sweeps_declare_identical_refs(self):
        d1, _ = self._sweep()
        d2, _ = self._sweep()
        assert d1.source_ref == d2.source_ref
        assert d1.commitment == d2.commitment

    def test_redacted_summary_is_counts_only(self):
        declaration, _ = self._sweep()
        assert "1 new" in declaration.redacted_summary
        assert "1 changed" in declaration.redacted_summary
        for leak in ("Alice", "Carol", "alice@", "carol@"):
            assert leak not in declaration.redacted_summary

    def test_empty_delta_declares_nothing_by_default(self):
        local = [_contact("c1", "Alice", "alice@x.com", last_contacted=NOW)]
        remote = [_dex_contact("c1", "Alice", "alice@x.com")]
        sweep = DexSweep(stash={}, now=lambda: NOW)
        assert sweep.run(remote, local, neglect_days=90) is None


class TestAdapterProvesTheClaim:
    def _command(self, declaration) -> JobSearchCommandV1:
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

    @pytest.mark.asyncio
    async def test_adapter_returns_result_matching_command_claim(self):
        local = [_contact("c1", "Alice", "alice@x.com")]
        remote = [_dex_contact("c3", "Carol", "carol@x.com")]
        stash: dict[str, dict] = {}
        declaration = DexSweep(stash=stash, now=lambda: NOW).run(remote, local, neglect_days=90)

        adapter = DexDeltaSourceAdapter(stash=stash)
        result = await adapter.ingest(self._command(declaration))

        assert result.source_kind == declaration.source_kind
        assert result.source_ref == declaration.source_ref
        assert result.observed_at == declaration.observed_at
        assert result.commitment == declaration.commitment
        assert result.evidence_id.startswith("evidence-")

    @pytest.mark.asyncio
    async def test_adapter_refuses_a_claim_it_cannot_prove(self):
        adapter = DexDeltaSourceAdapter(stash={})
        declaration_like = type("D", (), {
            "source_kind": "dex",
            "source_ref": "dex-sweep:20260814:aaaaaaaaaaaa",
            "observed_at": "2026-08-14T06:00:00Z",
        })()
        with pytest.raises(DomainRefusal):
            await adapter.ingest(self._command(declaration_like))
