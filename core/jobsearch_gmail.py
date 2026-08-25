"""Gmail Sense adapter — Sense #2 of the AAL career vertical.

Reads only an authorized job-search query. UltraDex stores opaque thread IDs,
a commitment, and a counts-only summary. Subjects, senders, and bodies stay
in Gmail.

Authority: ADR-014 → PRD F4 → operator 2026-08-22 ("start with gmail").
source_kind "gmail" is already frozen in ravenhelm_contracts.jobsearch_v1.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, MutableMapping, Sequence

from ravenhelm_contracts.jobsearch_v1 import JobSearchCommandV1

from .jobsearch_executors import DomainRefusal, EvidenceIngestResult
from .jobsearch_sources import SweepDeclaration, SweepStash

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailAuthError(Exception):
    """Credential resolution failed. reason_code is safe to log; values are not."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code

# Authorized job-search mail only — not the inbox. ATS + interview/application
# language. Marketing/notification labels excluded when present.
DEFAULT_GMAIL_SENSE_QUERY = (
    "newer_than:60d -label:Marketing -label:Notification "
    "(from:greenhouse.io OR from:lever.co OR from:ashbyhq.com "
    "OR from:icims.com OR from:myworkday.com OR from:smartrecruiters.com "
    "OR from:jobvite.com "
    "OR subject:interview OR subject:recruiter "
    'OR subject:"application received" OR subject:"thank you for applying" '
    'OR subject:"job opportunity" OR subject:"next steps")'
)


def _canonical_payload(query: str, thread_ids: Sequence[str]) -> str:
    body = {"query": query, "thread_ids": list(thread_ids)}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_thread_ids(thread_ids: Sequence[str]) -> list[str]:
    return sorted({tid.strip() for tid in thread_ids if tid and tid.strip()})


@dataclass(frozen=True)
class GmailSweep:
    """Runs the Gmail sense sweep, stashes the payload, returns the declaration."""

    stash: SweepStash | MutableMapping[str, dict]
    now: Callable[[], datetime]

    def run(
        self,
        thread_ids: Sequence[str],
        *,
        query: str,
        deposit_empty: bool = False,
    ) -> SweepDeclaration | None:
        ids = normalize_thread_ids(thread_ids)
        if not ids and not deposit_empty:
            return None

        moment = self.now()
        payload = _canonical_payload(query, ids)
        digest = _digest(payload)
        declaration = SweepDeclaration(
            source_kind="gmail",
            source_ref=f"gmail-sweep:{moment.strftime('%Y%m%d')}:{digest[:12]}",
            observed_at=_timestamp(moment),
            commitment=f"sha256:{digest}",
            redacted_summary=f"gmail sweep: {len(ids)} threads",
        )
        self.stash[declaration.source_ref] = {
            "payload": payload,
            "commitment": declaration.commitment,
            "observed_at": declaration.observed_at,
            "redacted_summary": declaration.redacted_summary,
        }
        return declaration


class GmailSourceAdapter:
    """Proves a pre-declared gmail sources.ingest claim from the stash."""

    def __init__(self, *, stash: SweepStash | MutableMapping[str, dict]) -> None:
        self._stash = stash

    async def ingest(self, command: JobSearchCommandV1) -> EvidenceIngestResult:
        source_kind = command.parameters.get("source_kind")
        source_ref = command.parameters.get("source_ref")
        observed_at = command.parameters.get("observed_at")
        if source_kind != "gmail":
            raise DomainRefusal("gmail_adapter_wrong_source_kind")
        if not source_ref or not observed_at:
            raise DomainRefusal("gmail_ingest_missing_declaration")

        stashed = self._stash.get(source_ref)
        if stashed is None:
            raise DomainRefusal("gmail_sweep_unproven_claim")
        if stashed["observed_at"] != observed_at:
            raise DomainRefusal("gmail_sweep_observed_at_mismatch")
        if f"sha256:{_digest(stashed['payload'])}" != stashed["commitment"]:
            raise DomainRefusal("gmail_sweep_payload_tampered")

        digest12 = stashed["commitment"].removeprefix("sha256:")[:12]
        return EvidenceIngestResult(
            evidence_id=f"evidence-gmail-{digest12}",
            source_kind="gmail",
            source_ref=source_ref,
            observed_at=observed_at,
            commitment=stashed["commitment"],
            redacted_summary=stashed["redacted_summary"],
        )


def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    client,
) -> str:
    """Exchange a refresh token for a short-lived access token. Returns the token only."""
    response = client.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if response.status_code == 400:
        try:
            error = (response.json() or {}).get("error")
        except ValueError:
            error = None
        if error == "invalid_grant":
            raise GmailAuthError("gmail_refresh_invalid_grant")
        raise GmailAuthError("gmail_refresh_rejected")
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise GmailAuthError("gmail_refresh_malformed") from exc
    access = payload.get("access_token")
    if not access:
        raise GmailAuthError("gmail_refresh_missing_access_token")
    return str(access)


def resolve_access_token(*, environ: MutableMapping[str, str], client) -> str:
    """Prefer GMAIL_ACCESS_TOKEN; otherwise refresh from client + refresh token."""
    direct = (environ.get("GMAIL_ACCESS_TOKEN") or "").strip()
    if direct:
        return direct
    client_id = (environ.get("GMAIL_CLIENT_ID") or "").strip()
    client_secret = (environ.get("GMAIL_CLIENT_SECRET") or "").strip()
    refresh_token = (environ.get("GMAIL_REFRESH_TOKEN") or "").strip()
    if not (client_id and client_secret and refresh_token):
        raise GmailAuthError("gmail_credentials_missing")
    return refresh_access_token(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        client=client,
    )


def fetch_thread_ids(
    *,
    access_token: str,
    query: str,
    client,
    max_pages: int = 4,
) -> list[str]:
    """List Gmail thread IDs for `query`. Returns IDs only — no subjects."""
    ids: list[str] = []
    page_token = None
    for _ in range(max_pages):
        params: dict[str, str | int] = {
            "userId": "me",
            "q": query,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        response = client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/threads",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        for thread in payload.get("threads") or []:
            thread_id = thread.get("id")
            if thread_id:
                ids.append(str(thread_id))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return normalize_thread_ids(ids)
