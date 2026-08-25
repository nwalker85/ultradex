"""Gmail sweep runner — ambient half of Sense #2.

Sweep → stash → declare → submit. The command carries only
(source_kind, source_ref, observed_at). Thread IDs wait in the stash.

    python -m cli.sense_gmail --dry-run
    python -m cli.sense_gmail --thread-ids-file /path/ids.txt
    python -m cli.sense_gmail
        # GMAIL_ACCESS_TOKEN, or GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET
        # + GMAIL_REFRESH_TOKEN (1Password: Gmail OAuth - CCC Sense)

Env: REDIS_URL, ULTRADEX_API_BASE, ULTRADEX_API_TOKEN,
GMAIL_ACCESS_TOKEN or refresh-token trio, GMAIL_SENSE_QUERY.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.jobsearch_gmail import (
    DEFAULT_GMAIL_SENSE_QUERY,
    GmailAuthError,
    GmailSweep,
    fetch_thread_ids,
    resolve_access_token,
)
from core.jobsearch_sources import RedisSweepStash


def _ids_from_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Gmail sense sweep")
    parser.add_argument("--query", default=os.getenv("GMAIL_SENSE_QUERY", DEFAULT_GMAIL_SENSE_QUERY))
    parser.add_argument("--thread-ids-file", type=Path)
    parser.add_argument("--deposit-empty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stash = RedisSweepStash.from_env()
    if stash is None:
        print("REDIS_URL is required (the worker proves claims from the stash)",
              file=sys.stderr)
        return 2

    if args.thread_ids_file is not None:
        thread_ids = _ids_from_file(args.thread_ids_file)
    else:
        try:
            with httpx.Client() as client:
                token = resolve_access_token(environ=os.environ, client=client)
                thread_ids = fetch_thread_ids(
                    access_token=token,
                    query=args.query,
                    client=client,
                )
        except GmailAuthError as exc:
            print(exc.reason_code, file=sys.stderr)
            return 2

    print(f"swept: {len(thread_ids)} thread ids")

    declaration = GmailSweep(
        stash=stash,
        now=lambda: datetime.now(timezone.utc),
    ).run(thread_ids, query=args.query, deposit_empty=args.deposit_empty)
    if declaration is None:
        print("empty sweep — nothing declared (use --deposit-empty to record quiet)")
        return 0

    print(f"declared: {declaration.source_ref}")
    print(f"          {declaration.commitment}")
    print(f"          {declaration.redacted_summary}")

    if args.dry_run:
        print("dry run — no command submitted")
        return 0

    token = os.getenv("ULTRADEX_COMMAND_TOKEN") or os.getenv("ULTRADEX_API_TOKEN")
    if not token:
        print("ULTRADEX_COMMAND_TOKEN or ULTRADEX_API_TOKEN required to submit",
              file=sys.stderr)
        return 2
    base = os.getenv("ULTRADEX_API_BASE", "http://127.0.0.1:8000")

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{base}/api/v2/job-search/commands/sources.ingest",
            json={
                "source_kind": declaration.source_kind,
                "source_ref": declaration.source_ref,
                "observed_at": declaration.observed_at,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"sense-gmail-{uuid.uuid4()}",
            },
        )
    print(f"submitted: HTTP {response.status_code}")
    print(response.text[:400])
    return 0 if response.status_code == 202 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
