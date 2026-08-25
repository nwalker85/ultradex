"""Backfill orchestration for the mail corpus Stage.

Newest-first, page by page, writing each page before asking for the next — so
the corpus is queryable within a minute instead of after the full three-year
pull completes. Idempotent by construction: already-ingested message IDs are
skipped before they are fetched, and ReplacingMergeTree collapses whatever
still overlaps.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .mail_clickhouse import MailCorpusWriter, WriteResult
from .mail_corpus import (
    DEFAULT_MAX_BODY_CHARS,
    MailChunk,
    MailMessage,
    part_histogram,
    segment_message,
)
from .mail_gmail import (
    DEFAULT_MAIL_CORPUS_QUERY,
    DEFAULT_PAGE_SIZE,
    fetch_messages,
    iter_message_id_pages,
)


@dataclass(frozen=True)
class IngestPlan:
    """What this run is allowed to do. All of it is caller-supplied."""

    query: str = DEFAULT_MAIL_CORPUS_QUERY
    page_size: int = DEFAULT_PAGE_SIZE
    max_messages: int | None = None
    max_pages: int | None = None
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS
    include_spam_trash: bool = False
    skip_existing: bool = True
    dry_run: bool = False


@dataclass
class IngestReport:
    """Counts only — no subjects, no bodies. Safe to print to a terminal."""

    pages: int = 0
    ids_listed: int = 0
    messages_skipped: int = 0
    messages_fetched: int = 0
    messages_written: int = 0
    chunks_written: int = 0
    parts: dict[str, int] = field(default_factory=dict)
    template_ids: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @property
    def embeddable_chunks(self) -> int:
        return self.parts.get("subject", 0) + self.parts.get("body", 0)

    def summary_lines(self) -> list[str]:
        lines = [
            f"pages={self.pages} listed={self.ids_listed} "
            f"skipped={self.messages_skipped} fetched={self.messages_fetched}",
            f"written: messages={self.messages_written} chunks={self.chunks_written} "
            f"embeddable={self.embeddable_chunks} templates={len(self.template_ids)}",
        ]
        if self.parts:
            parts = " ".join(
                f"{part}={count}" for part, count in sorted(self.parts.items()) if count
            )
            lines.append(f"parts: {parts}")
        if self.errors:
            lines.append(f"errors={len(self.errors)}: {', '.join(self.errors[:5])}")
        return lines


def _merge_histogram(target: dict[str, int], chunks: Sequence[MailChunk]) -> None:
    for part, count in part_histogram(chunks).items():
        if count:
            target[part] = target.get(part, 0) + count


def ingest_pages(
    *,
    access_token: str,
    http_client,
    writer: MailCorpusWriter | None,
    plan: IngestPlan,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = lambda _message: None,
) -> IngestReport:
    """Run the backfill. ``writer`` may be ``None`` when ``plan.dry_run``."""
    if writer is None and not plan.dry_run:
        raise ValueError("a writer is required unless plan.dry_run is set")

    report = IngestReport()
    remaining = plan.max_messages

    for page_ids in iter_message_id_pages(
        access_token=access_token,
        query=plan.query,
        client=http_client,
        page_size=plan.page_size,
        max_pages=plan.max_pages,
        include_spam_trash=plan.include_spam_trash,
        sleep=sleep,
    ):
        report.pages += 1
        report.ids_listed += len(page_ids)

        wanted = list(page_ids)
        if plan.skip_existing and writer is not None:
            known = writer.existing_message_ids(wanted)
            if known:
                report.messages_skipped += len(known)
                wanted = [mid for mid in wanted if mid not in known]

        if remaining is not None:
            wanted = wanted[: max(remaining, 0)]

        if wanted:
            messages: list[MailMessage] = fetch_messages(
                wanted,
                access_token=access_token,
                client=http_client,
                sleep=sleep,
                on_error=lambda mid, exc: report.errors.append(f"{mid}:{exc}"),
            )
            report.messages_fetched += len(messages)

            chunks: list[MailChunk] = []
            for message in messages:
                chunks.extend(
                    segment_message(message, max_body_chars=plan.max_body_chars)
                )
            _merge_histogram(report.parts, chunks)
            report.template_ids.update(
                chunk.template_id for chunk in chunks if chunk.template_id
            )

            if plan.dry_run or writer is None:
                result = WriteResult()
            else:
                result = writer.write(messages, chunks)
            report.messages_written += result.messages_written
            report.chunks_written += result.chunks_written

            if remaining is not None:
                remaining -= len(wanted)

        log(
            f"page {report.pages}: listed={len(page_ids)} "
            f"fetched={report.messages_fetched} written={report.messages_written} "
            f"chunks={report.chunks_written}"
        )

        if remaining is not None and remaining <= 0:
            break

    return report
