"""Surface owed replies from the mail corpus and post them to Odin's Runes.

    op run --env-file=scripts/mail-corpus.env.tpl -- \\
        python -m cli.owed_replies --dry-run

Environment (all resolved by `op run`; nothing on argv):

    MAIL_CLICKHOUSE_URL / _DATABASE / _USER / _PASSWORD   the read-side corpus
    MAIL_CLICKHOUSE_DATABASES   optional comma list of per-account databases to union
                                (overrides _DATABASE for reads; e.g. gmailnwalker85,gmailnateravenhelmco)
    MAIL_OWNER_ADDRESSES        comma-separated; the operator's own addresses
    CCC_API_URL                 e.g. http://10.10.20.101:30800
    ULTRADEX_API_TOKEN          bearer for the CCC contacts read
    CCC_CONTACTS_FILE           optional: a saved /api/v1/contacts JSON array; when set the
                                CCC API is not called (for hosts the NetworkPolicy excludes)
    ODINSRUNES_API_URL          e.g. http://10.10.20.102:8765
    ODINSRUNES_API_TOKEN        optional bearer (hub gate is open when unset)

Exit codes: 0 ran, 2 configuration refused, 3 a remote refused us.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Mapping

import httpx

from core.jobsearch_executors import DomainRefusal
from core.mail_ranking import RankerConfig, StupidRanker
from core.mail_reads import ClickHouseMailCorpus, MailCorpusUnavailable
from core.owed_replies import (
    TASK_ID_PREFIX,
    TASK_SOURCE,
    CccContactDirectory,
    ContactRow,
    ObservingCorpus,
    UnionCorpus,
    plan_sync,
)


def build_corpus(http: httpx.Client, environ: Mapping[str, str]):
    names = [n.strip() for n in environ.get("MAIL_CLICKHOUSE_DATABASES", "").split(",") if n.strip()]
    if not names:
        return ClickHouseMailCorpus.from_env(client=http, environ=environ)
    corpora = []
    for name in names:
        scoped = dict(environ)
        scoped["MAIL_CLICKHOUSE_DATABASE"] = name
        corpora.append(ClickHouseMailCorpus.from_env(client=http, environ=scoped))
    return UnionCorpus(corpora)


def _require(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        print(f"refused: {name} is not set", file=sys.stderr)
        sys.exit(2)
    return value


def _contact_rows(items) -> list[ContactRow]:
    return [
        ContactRow(id=str(i.get("id")), name=i.get("name") or "", email=i.get("email"),
                   company=i.get("company"), job_title=i.get("job_title"))
        for i in items
    ]


def load_contacts_file(path: str) -> list[ContactRow]:
    with open(path, encoding="utf-8") as fh:
        return _contact_rows(json.load(fh))


def load_contacts(client: httpx.Client, *, base_url: str, token: str) -> list[ContactRow]:
    response = client.get(
        base_url.rstrip("/") + "/api/v1/contacts",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    if response.status_code != 200:
        print(f"refused: ccc contacts read -> HTTP {response.status_code}", file=sys.stderr)
        sys.exit(3)
    return _contact_rows(response.json())


def _hub_error(body: dict) -> str:
    """The hub's error code, clamped: one line, ASCII-ish, short. Never echo a server
    field verbatim into the terminal."""
    raw = body.get("error", "") if isinstance(body, dict) else ""
    text = "".join(ch if ch.isprintable() else " " for ch in str(raw))
    return " ".join(text.split())[:120]


def existing_hub_tasks(client: httpx.Client, *, base_url: str, headers: dict) -> dict[str, str]:
    """Hub task id -> status for every task this producer has posted."""
    response = client.get(
        base_url.rstrip("/") + "/api/tasks",
        params={"source": TASK_SOURCE, "limit": 1000},
        headers=headers,
        timeout=20.0,
    )
    if response.status_code != 200:
        print(f"refused: hub tasks read -> HTTP {response.status_code}", file=sys.stderr)
        sys.exit(3)
    return {
        str(item.get("action_id") or item.get("id")): str(item.get("status") or "")
        for item in response.json().get("items", [])
        if str(item.get("action_id") or item.get("id")).startswith(TASK_ID_PREFIX)
    }


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    environ = environ if environ is not None else os.environ
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the plan; post nothing")
    parser.add_argument("--include-arrivals", action="store_true", help="also post surfaced arrivals, not only owed replies")
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=5000,
                        help="row cap per corpus read; a hit cap truncates the window and is reported")
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

    try:
        config = RankerConfig.from_env(environ)
    except ValueError as exc:
        print(f"refused: ranker config: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    with httpx.Client() as http:
        rows = load_contacts_file(contacts_file) if contacts_file else load_contacts(http, base_url=ccc_url, token=ccc_token)
        directory = CccContactDirectory.from_rows(rows)
        corpus = ObservingCorpus(build_corpus(http, environ), directory)
        ranker = StupidRanker(corpus=corpus, contacts=directory, config=config)
        try:
            results = ranker.surface(now=now, window_days=args.window_days, limit=args.limit)
            if ranker.last_read_truncated:
                print(f"warning: corpus reads hit the row cap ({args.limit}) for: "
                      f"{', '.join(ranker.last_read_truncated)} — the window is truncated; raise --limit",
                      file=sys.stderr)
        except DomainRefusal as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        except MailCorpusUnavailable as exc:
            print(f"refused: corpus: {exc.reason_code}", file=sys.stderr)
            return 3

        existing = existing_hub_tasks(http, base_url=hub_url, headers=hub_headers)
        plan = plan_sync(results, directory=directory, existing_task_ids=existing, include_arrivals=args.include_arrivals)

        posted: list[str] = []
        updated: list[str] = []
        failed: list[str] = []
        if not args.dry_run:
            for payload in plan.create:
                response = http.post(hub_url.rstrip("/") + "/api/tasks", json=payload, headers=hub_headers, timeout=20.0)
                body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if response.status_code == 200 and body.get("ok"):
                    posted.append(payload["id"])
                else:
                    failed.append(f"{payload['id']}: HTTP {response.status_code} {_hub_error(body)}".strip())
            for patch in plan.update:
                body_out = {"title": patch["title"], "description": patch["description"]}
                response = http.patch(hub_url.rstrip("/") + "/api/tasks/" + patch["id"], json=body_out,
                                      headers=hub_headers, timeout=20.0)
                body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if response.status_code == 200 and body.get("ok"):
                    updated.append(patch["id"])
                else:
                    failed.append(f"{patch['id']} (update): HTTP {response.status_code} {_hub_error(body)}".strip())

    summary = {
        "now": now.isoformat(),
        "ranked": len(results),
        "surfaced": sum(1 for r in results if r.surfaced),
        "owed": sum(1 for r in results if r.is_owed_reply),
        "to_create": [p["title"] for p in plan.create],
        "to_update": [{"id": u["id"], "title": u["title"]} for u in plan.update],
        "skipped_existing": list(plan.skipped_existing),
        "ignored_arrivals": len(plan.ignored),
        "posted": posted,
        "updated": updated,
        "failed": failed,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"ranked={summary['ranked']} surfaced={summary['surfaced']} owed={summary['owed']} "
              f"create={len(plan.create)} update={len(plan.update)} skipped={len(plan.skipped_existing)} "
              f"posted={len(posted)} updated={len(updated)} failed={len(failed)}"
              f"{' (dry run)' if args.dry_run else ''}")
        for payload in plan.create:
            print(f"  + {payload['id']}  [{payload['priority']}]  {payload['title']}")
        for patch in plan.update:
            print(f"  ~ {patch['id']}  {patch['title']}")
        for line in failed:
            print(f"  ! {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
