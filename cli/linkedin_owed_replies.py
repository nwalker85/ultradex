"""Scan the signed-in LinkedIn inbox (via the mcp-chrome bridge) and post owed
replies to Odin's Runes.

    python -m cli.linkedin_owed_replies --dry-run

Environment:

    MCP_CHROME_URL              bridge endpoint (default http://127.0.0.1:12306/mcp)
    MCP_CHROME_TAB_ID           optional: reuse an existing LinkedIn tab id
    MCP_CHROME_SESSION_ID       optional: the bridge holds ONE session; reuse it
    MCP_CHROME_SESSION_FILE     where the session id is shared (default ~/var/mcp-chrome/session-id)
    CCC_API_URL / ULTRADEX_API_TOKEN   CCC contacts read (or CCC_CONTACTS_FILE)
    CCC_CONTACTS_FILE           optional saved /api/v1/contacts JSON array
    ODINSRUNES_API_URL          e.g. http://10.10.20.102:8765
    ODINSRUNES_API_TOKEN        optional bearer
    LINKEDIN_GRACE_HOURS        default 24 (known contact); cold contacts wait 72

Laptop-bound by construction: the bridge lives in Nate's Chrome. DOM-only and
background throughout; the window never gains focus.

Exit codes: 0 ran, 2 configuration refused, 3 a remote refused us.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Mapping

import httpx

from cli.owed_replies import _hub_error, _require, load_contacts, load_contacts_file
from core.linkedin_owed_replies import TASK_ID_PREFIX, TASK_SOURCE, plan_sync, rank
from core.linkedin_reads import BridgeUnavailable, ChromeBridge, LinkedInInbox
from core.owed_replies import CccContactDirectory


def existing_hub_tasks(client: httpx.Client, *, base_url: str, headers: dict) -> dict[str, dict]:
    response = client.get(base_url.rstrip("/") + "/api/tasks", params={"source": TASK_SOURCE, "limit": 1000},
                          headers=headers, timeout=20.0)
    if response.status_code != 200:
        print(f"refused: hub tasks read -> HTTP {response.status_code}", file=sys.stderr)
        sys.exit(3)
    out: dict[str, dict] = {}
    for item in response.json().get("items", []):
        task_id = str(item.get("action_id") or item.get("id"))
        if not task_id.startswith(TASK_ID_PREFIX):
            continue
        meta = item.get("raw_metadata") or {}
        out[task_id] = {"status": str(item.get("status") or ""), "thread_url": meta.get("thread_url") or "",
                        "contact_name": item.get("contact_name") or ""}
    return out


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    environ = environ if environ is not None else os.environ
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the plan; post nothing")
    parser.add_argument("--limit", type=int, default=50, help="threads to consider from the top of the list")
    parser.add_argument("--json", action="store_true", help="machine-readable summary on stdout")
    args = parser.parse_args(argv)

    contacts_file = environ.get("CCC_CONTACTS_FILE", "").strip()
    if not contacts_file:
        ccc_url = _require(environ, "CCC_API_URL")
        ccc_token = _require(environ, "ULTRADEX_API_TOKEN")
    hub_url = _require(environ, "ODINSRUNES_API_URL")
    hub_headers = {}
    if environ.get("ODINSRUNES_API_TOKEN"):
        hub_headers["Authorization"] = f"Bearer {environ['ODINSRUNES_API_TOKEN']}"
    bridge_url = environ.get("MCP_CHROME_URL", "").strip() or "http://127.0.0.1:12306/mcp"
    session_id = environ.get("MCP_CHROME_SESSION_ID", "").strip() or None
    session_file = environ.get("MCP_CHROME_SESSION_FILE", "").strip() or "~/var/mcp-chrome/session-id"
    tab_id = int(environ["MCP_CHROME_TAB_ID"]) if environ.get("MCP_CHROME_TAB_ID", "").strip() else None
    grace = timedelta(hours=float(environ.get("LINKEDIN_GRACE_HOURS", "24") or 24))

    now = datetime.now(timezone.utc)
    with httpx.Client() as http:
        rows = load_contacts_file(contacts_file) if contacts_file else load_contacts(http, base_url=ccc_url, token=ccc_token)
        directory = CccContactDirectory.from_rows(rows)
        inbox = LinkedInInbox(ChromeBridge(http, url=bridge_url, session_id=session_id, session_file=session_file), tab_id=tab_id)
        try:
            threads = inbox.read_inbox(now=now)[: args.limit]
        except BridgeUnavailable as exc:
            print(f"refused: bridge: {exc.reason}", file=sys.stderr)
            return 3
        ranked = rank(threads, directory=directory, now=now, grace=grace)
        # Resolve thread URLs only for the owed candidates (one DOM click each).
        try:
            owed_threads = inbox.resolve_thread_urls([r.thread for r in ranked if r.owed])
        except BridgeUnavailable as exc:
            print(f"refused: bridge: {exc.reason}", file=sys.stderr)
            return 3
        by_index = {t.row_index: t for t in owed_threads}
        ranked = [type(r)(by_index.get(r.thread.row_index, r.thread), r.owed, r.age, r.known, r.reason) if r.owed else r for r in ranked]
        existing = existing_hub_tasks(http, base_url=hub_url, headers=hub_headers)
        plan = plan_sync(ranked, directory=directory, existing=existing)

        posted: list[str] = []
        closed: list[str] = []
        failed: list[str] = []
        if not args.dry_run:
            for payload in plan.create:
                response = http.post(hub_url.rstrip("/") + "/api/tasks", json=payload, headers=hub_headers, timeout=20.0)
                body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if response.status_code == 200 and body.get("ok"):
                    posted.append(payload["id"])
                else:
                    failed.append(f"{payload['id']}: HTTP {response.status_code} {_hub_error(body)}".strip())
            for task_id in plan.close:
                response = http.patch(hub_url.rstrip("/") + "/api/tasks/" + task_id,
                                      json={"status": "completed"}, headers=hub_headers, timeout=20.0)
                body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if response.status_code == 200 and body.get("ok"):
                    closed.append(task_id)
                else:
                    failed.append(f"{task_id} (close): HTTP {response.status_code} {_hub_error(body)}".strip())

    summary = {
        "now": now.isoformat(),
        "threads": len(threads),
        "owed": sum(1 for r in ranked if r.owed),
        "to_create": [p["title"] for p in plan.create],
        "to_close": plan.close,
        "skipped": len(plan.skipped),
        "posted": posted,
        "closed": closed,
        "failed": failed,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"threads={summary['threads']} owed={summary['owed']} create={len(plan.create)} "
              f"close={len(plan.close)} skipped={summary['skipped']} posted={len(posted)} "
              f"closed={len(closed)} failed={len(failed)}" + (" (dry run)" if args.dry_run else ""))
        for r in ranked:
            mark = "+" if r.owed else "·"
            print(f"  {mark} {r.thread.counterparty:<28} {r.thread.last_message_from:<4} {r.thread.time_label:<10} {r.reason}")
        for line in failed:
            print("  ! " + line)
    return 0 if not failed else 3


if __name__ == "__main__":
    sys.exit(main())
