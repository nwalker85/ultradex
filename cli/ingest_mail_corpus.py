"""Gmail → ClickHouse mail corpus ingest — the private Stage backfill.

    # 0. see the schema without touching a server
    python -m cli.ingest_mail_corpus --print-ddl

    # 1. create database + tables (idempotent)
    python -m cli.ingest_mail_corpus --init-schema

    # 2. look before you leap: fetch + segment, write nothing
    python -m cli.ingest_mail_corpus --dry-run --max-messages 20

    # 3. small verified sample, then the real backfill (newest-first)
    python -m cli.ingest_mail_corpus --max-messages 50
    python -m cli.ingest_mail_corpus            # full 3-year window

Gmail auth reuses the governed sense credentials (1Password
``op://ravenmask/Gmail OAuth - CCC Sense``):
``GMAIL_ACCESS_TOKEN`` or ``GMAIL_CLIENT_ID`` + ``GMAIL_CLIENT_SECRET`` +
``GMAIL_REFRESH_TOKEN``.

ClickHouse has **no credential default** — ``MAIL_CLICKHOUSE_USER`` and
``MAIL_CLICKHOUSE_PASSWORD`` are required, because the ``default`` user on vakr
reaches every database on the host. Naming the user is an operator decision.
Optional: ``MAIL_CLICKHOUSE_URL`` (default ``http://vakr.ravenmask.net:8123``),
``MAIL_CLICKHOUSE_DATABASE`` (default ``gmailnwalker85`` — one database per
mail account), ``MAIL_CLICKHOUSE_TIMEOUT``.
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx

from core.jobsearch_gmail import GmailAuthError, resolve_access_token
from core.mail_clickhouse import (
    DEFAULT_DATABASE,
    ClickHouseConfig,
    ClickHouseError,
    MailClickHouseClient,
    MailCorpusWriter,
    MailClickHouseConfigError,
    schema_statements,
)
from core.mail_corpus import DEFAULT_MAX_BODY_CHARS
from core.mail_gmail import (
    DEFAULT_CORPUS_WINDOW_YEARS,
    DEFAULT_PAGE_SIZE,
    GmailFetchError,
    corpus_query,
)
from core.mail_ingest import IngestPlan, ingest_pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill the private Gmail mail corpus into ClickHouse",
    )
    parser.add_argument("--print-ddl", action="store_true",
                        help="print the DDL and exit — touches nothing")
    parser.add_argument("--init-schema", action="store_true",
                        help="apply the DDL (idempotent) before ingesting")
    parser.add_argument("--schema-only", action="store_true",
                        help="apply the DDL and exit without ingesting")
    parser.add_argument("--query", default=os.getenv("MAIL_CORPUS_QUERY"),
                        help="Gmail search query (default: newer_than:<years>y)")
    parser.add_argument("--years", type=int, default=DEFAULT_CORPUS_WINDOW_YEARS,
                        help="corpus window in years (default: 3)")
    parser.add_argument("--extra-query", default="",
                        help="extra Gmail query terms appended to the window")
    parser.add_argument("--resume", action="store_true",
                        help="continue the newest-first backfill from the oldest row already stored")
    parser.add_argument("--max-messages", type=int, default=None,
                        help="stop after this many newly fetched messages")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-body-chars", type=int, default=DEFAULT_MAX_BODY_CHARS,
                        help="split body spans longer than this on paragraph boundaries")
    parser.add_argument("--include-spam-trash", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="re-fetch and re-write messages already in the corpus")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and segment, write nothing")
    parser.add_argument("--counts", action="store_true",
                        help="print corpus counts and exit")
    return parser


def _resolve_config() -> ClickHouseConfig | None:
    try:
        return ClickHouseConfig.from_env(os.environ)
    except MailClickHouseConfigError as exc:
        print(exc.reason_code, file=sys.stderr)
        print(
            "set MAIL_CLICKHOUSE_USER and MAIL_CLICKHOUSE_PASSWORD "
            "(1Password: op://ravenmask/Heimdall ClickStack - Vakr) — there is no default",
            file=sys.stderr,
        )
        return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.print_ddl:
        database = os.getenv("MAIL_CLICKHOUSE_DATABASE") or DEFAULT_DATABASE
        for statement in schema_statements(database):
            print(statement.rstrip() + ";\n")
        return 0

    query = args.query or corpus_query(years=args.years, extra=args.extra_query)

    config = None
    needs_clickhouse = not (args.dry_run and not args.init_schema and not args.counts)
    if needs_clickhouse:
        config = _resolve_config()
        if config is None:
            return 2

    with httpx.Client() as http_client:
        writer: MailCorpusWriter | None = None
        if config is not None:
            client = MailClickHouseClient(config=config, client=http_client)
            writer = MailCorpusWriter(client)
            print(f"clickhouse: {config.describe()}")
            try:
                if args.init_schema or args.schema_only:
                    for applied in client.apply_schema():
                        print(f"  ddl: {applied}")
                if args.schema_only:
                    return 0
                if args.counts:
                    for key, value in sorted(writer.corpus_counts().items()):
                        print(f"  {key}={value}")
                    return 0
                if args.resume:
                    checkpoint = writer.oldest_ingested_ts()
                    if checkpoint is not None:
                        query = corpus_query(
                            years=args.years,
                            before=checkpoint,
                            extra=args.extra_query,
                        )
                        print(f"resuming before {checkpoint.date().isoformat()}")
            except (ClickHouseError, MailClickHouseConfigError) as exc:
                print(str(exc), file=sys.stderr)
                return 1

        print(f"query: {query}")

        try:
            token = resolve_access_token(environ=os.environ, client=http_client)
        except GmailAuthError as exc:
            print(exc.reason_code, file=sys.stderr)
            return 2

        plan = IngestPlan(
            query=query,
            page_size=args.page_size,
            max_messages=args.max_messages,
            max_pages=args.max_pages,
            max_body_chars=args.max_body_chars,
            include_spam_trash=args.include_spam_trash,
            skip_existing=not args.force,
            dry_run=args.dry_run,
        )

        try:
            report = ingest_pages(
                access_token=token,
                http_client=http_client,
                writer=writer,
                plan=plan,
                log=lambda message: print(message, flush=True),
            )
        except (GmailFetchError, ClickHouseError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if plan.dry_run:
        print("dry run — nothing written")
    for line in report.summary_lines():
        print(line)
    return 1 if report.errors and not report.messages_written else 0


if __name__ == "__main__":
    raise SystemExit(main())
