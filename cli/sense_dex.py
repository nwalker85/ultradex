"""Dex-delta sweep runner — the ambient half of Sense #1 (WP5).

Sweep → stash → declare → submit. The command this submits carries only the
declaration (source_kind, source_ref, observed_at); the payload waits in the
stash for the worker's adapter to prove. Run from the host:

    python -m cli.sense_dex --dry-run          # sweep + declare, no command
    python -m cli.sense_dex                    # sweep + submit sources.ingest

Env: DEX_API_KEY, DATABASE_URL, REDIS_URL, ULTRADEX_API_BASE,
ULTRADEX_COMMAND_TOKEN (falls back to ULTRADEX_API_TOKEN).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx

from core.database import Database
from core.dex_client import DexClient
from core.models import ContactDB
from core.jobsearch_sources import DexSweep, RedisSweepStash


def _local_contacts(database_url: str) -> list[dict]:
    database = Database(database_url)
    database.init()
    session = database.get_session()
    try:
        rows = session.query(ContactDB).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "email": row.email,
                "phone": row.phone,
                "last_contacted": row.last_contacted,
            }
            for row in rows
        ]
    finally:
        session.close()
        database.close()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Dex-delta sense sweep")
    parser.add_argument("--neglect-days", type=int, default=90)
    parser.add_argument("--deposit-empty", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="sweep and declare, but submit no command")
    args = parser.parse_args()

    dex_api_key = os.getenv("DEX_API_KEY")
    if not dex_api_key:
        print("DEX_API_KEY is required", file=sys.stderr)
        return 2
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://ultradex:ultradex_dev_password@127.0.0.1:5432/ultradex",
    )
    stash = RedisSweepStash.from_env()
    if stash is None:
        print("REDIS_URL is required (the worker proves claims from the stash)",
              file=sys.stderr)
        return 2

    local = _local_contacts(database_url)
    remote = await DexClient(dex_api_key).fetch_all_contacts()
    print(f"swept: {len(remote)} remote / {len(local)} local contacts")

    declaration = DexSweep(stash=stash, now=lambda: datetime.now(timezone.utc)).run(
        remote, local,
        neglect_days=args.neglect_days,
        deposit_empty=args.deposit_empty,
    )
    if declaration is None:
        print("empty delta — nothing declared (use --deposit-empty to record quiet)")
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
                "Idempotency-Key": f"sense-dex-{uuid.uuid4()}",
            },
        )
    print(f"submitted: HTTP {response.status_code}")
    print(response.text[:400])
    return 0 if response.status_code == 202 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
