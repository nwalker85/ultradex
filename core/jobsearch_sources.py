"""Dex-delta Sense adapter — Sense #1 of the AAL career vertical (WP5).

Commit-then-execute: `DexSweep.run` computes the delta, stashes the canonical
payload, and returns a declaration. The submitted `sources.ingest` command
pre-declares (source_kind, source_ref, observed_at); `DexDeltaSourceAdapter`
proves that claim by retrieving the stashed payload — a claim it cannot prove
is refused, never repaired.

Authority: ADR-014 → PRD F4 → docs/prd/wp5-sense-dex-delta-brief.md.
No contract changes: `sources.ingest` and source kind "dex" are already frozen
in ravenhelm_contracts.jobsearch_v1.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, MutableMapping, Protocol, Sequence

from ravenhelm_contracts.jobsearch_v1 import JobSearchCommandV1

from .jobsearch_executors import DomainRefusal, EvidenceIngestResult

_CANONICAL_FIELDS = ("name", "email", "phone")


class SweepStash(Protocol):
    """Where a sweep parks its payload between declaration and execution."""

    def __setitem__(self, key: str, value: dict) -> None: ...
    def get(self, key: str) -> dict | None: ...


def _canonical_contact(contact) -> dict:
    """Normalize a contact (pydantic model or mapping) to comparable fields."""
    if hasattr(contact, "model_dump"):
        data = contact.model_dump()
    elif hasattr(contact, "dict"):
        data = contact.dict()
    else:
        data = dict(contact)
    return {field: (data.get(field) or None) for field in _CANONICAL_FIELDS} | {
        "id": str(data["id"])
    }


def compute_dex_delta(
    remote: Sequence,
    local: Sequence[Mapping],
    *,
    now: datetime,
    neglect_days: int,
) -> dict[str, list[dict]]:
    """Diff live Dex contacts against the locally synced table.

    new       — present in Dex, absent locally
    changed   — canonical field drift (name, email, phone)
    neglected — known locally, last_contacted beyond the threshold
    """
    local_by_id: dict[str, Mapping] = {str(c["id"]): c for c in local}
    delta: dict[str, list[dict]] = {"new": [], "changed": [], "neglected": []}

    for contact in remote:
        canonical = _canonical_contact(contact)
        known = local_by_id.get(canonical["id"])
        if known is None:
            delta["new"].append(canonical)
            continue
        known_canonical = _canonical_contact(known)
        if known_canonical != canonical:
            delta["changed"].append(canonical)
            continue
        last = known.get("last_contacted")
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is not None and (now - last).days > neglect_days:
            delta["neglected"].append(canonical)

    for bucket in delta.values():
        bucket.sort(key=lambda c: c["id"])
    return delta


def _canonical_payload(delta: Mapping[str, list[dict]]) -> str:
    return json.dumps(delta, sort_keys=True, separators=(",", ":"), default=str)


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class SweepDeclaration:
    """What the sweep commits to before any command is submitted."""

    source_kind: str
    source_ref: str
    observed_at: str
    commitment: str
    redacted_summary: str


class DexSweep:
    """Runs the delta, stashes the payload, returns the declaration."""

    def __init__(
        self,
        *,
        stash: SweepStash | MutableMapping[str, dict],
        now: Callable[[], datetime],
    ) -> None:
        self._stash = stash
        self._now = now

    def run(
        self,
        remote: Sequence,
        local: Sequence[Mapping],
        *,
        neglect_days: int,
        deposit_empty: bool = False,
    ) -> SweepDeclaration | None:
        moment = self._now()
        delta = compute_dex_delta(remote, local, now=moment, neglect_days=neglect_days)
        counts = {bucket: len(items) for bucket, items in delta.items()}
        if not deposit_empty and not any(counts.values()):
            return None

        payload = _canonical_payload(delta)
        digest = _digest(payload)
        declaration = SweepDeclaration(
            source_kind="dex",
            source_ref=f"dex-sweep:{moment.strftime('%Y%m%d')}:{digest[:12]}",
            observed_at=_timestamp(moment),
            commitment=f"sha256:{digest}",
            redacted_summary=(
                f"dex sweep: {counts['new']} new, {counts['changed']} changed, "
                f"{counts['neglected']} neglected"
            ),
        )
        self._stash[declaration.source_ref] = {
            "payload": payload,
            "commitment": declaration.commitment,
            "observed_at": declaration.observed_at,
            "redacted_summary": declaration.redacted_summary,
        }
        return declaration


class DexDeltaSourceAdapter:
    """SourceAdapter implementation: proves the command's declared claim."""

    def __init__(self, *, stash: SweepStash | MutableMapping[str, dict]) -> None:
        self._stash = stash

    async def ingest(self, command: JobSearchCommandV1) -> EvidenceIngestResult:
        source_kind = command.parameters.get("source_kind")
        source_ref = command.parameters.get("source_ref")
        observed_at = command.parameters.get("observed_at")
        if source_kind != "dex":
            raise DomainRefusal("dex_adapter_wrong_source_kind")
        if not source_ref or not observed_at:
            raise DomainRefusal("dex_ingest_missing_declaration")

        stashed = self._stash.get(source_ref)
        if stashed is None:
            raise DomainRefusal("dex_sweep_unproven_claim")
        if stashed["observed_at"] != observed_at:
            raise DomainRefusal("dex_sweep_observed_at_mismatch")
        if f"sha256:{_digest(stashed['payload'])}" != stashed["commitment"]:
            raise DomainRefusal("dex_sweep_payload_tampered")

        digest12 = stashed["commitment"].removeprefix("sha256:")[:12]
        return EvidenceIngestResult(
            evidence_id=f"evidence-dex-{digest12}",
            source_kind="dex",
            source_ref=source_ref,
            observed_at=observed_at,
            commitment=stashed["commitment"],
            redacted_summary=stashed["redacted_summary"],
        )


class RoutedSourceAdapter:
    """Dispatch sources.ingest to the adapter bound for source_kind."""

    def __init__(self, adapters: Mapping[str, object]) -> None:
        self._adapters = dict(adapters)

    async def ingest(self, command: JobSearchCommandV1) -> EvidenceIngestResult:
        source_kind = command.parameters.get("source_kind")
        adapter = self._adapters.get(str(source_kind) if source_kind else "")
        if adapter is None:
            raise DomainRefusal("source_adapter_unbound")
        return await adapter.ingest(command)


class RedisSweepStash:
    """Sweep stash shared between the host-side sweeper and the worker.

    Values are small JSON blobs keyed by source_ref; the TTL bounds how long a
    declaration may wait between sweep and command execution.
    """

    _PREFIX = "jobsearch:sense:"

    def __init__(self, client, *, ttl_seconds: int = 3600) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_env(cls) -> "RedisSweepStash | None":
        import os

        import redis as _redis

        url = os.getenv("REDIS_URL")
        if not url:
            return None
        return cls(_redis.Redis.from_url(url, decode_responses=True))

    def __setitem__(self, key: str, value: dict) -> None:
        self._client.setex(self._PREFIX + key, self._ttl, json.dumps(value))

    def get(self, key: str) -> dict | None:
        raw = self._client.get(self._PREFIX + key)
        return json.loads(raw) if raw else None
