"""Backfill orchestration — newest-first, idempotent, and safe to re-run."""
from __future__ import annotations

import base64

import pytest

from core.mail_clickhouse import MailCorpusWriter, WriteResult
from core.mail_ingest import IngestPlan, IngestReport, ingest_pages


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode().rstrip("=")


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers: dict[str, str] = {}

    def json(self):
        return self._payload


def _raw(message_id: str, body: str = "Hello there, quick update on the role.") -> dict:
    return {
        "id": message_id,
        "threadId": f"thr-{message_id}",
        "internalDate": "1756045800000",
        "labelIds": ["INBOX"],
        "snippet": body[:40],
        "sizeEstimate": 1024,
        "payload": {
            "headers": [
                {"name": "From", "value": "dana@acme.example"},
                {"name": "Subject", "value": f"Subject {message_id}"},
            ],
            "parts": [{"mimeType": "text/plain", "body": {"data": _b64(body)}}],
        },
    }


class ScriptedGmail:
    """Serves list pages then per-message fetches, newest-first."""

    def __init__(self, pages: list[tuple[list[str], str | None]], bodies: dict[str, str] | None = None):
        self._pages = list(pages)
        self._bodies = bodies or {}
        self.fetched: list[str] = []

    def get(self, url, *, params=None, headers=None, timeout=None):
        if url.endswith("/messages"):
            ids, token = self._pages.pop(0)
            payload: dict = {"messages": [{"id": mid} for mid in ids]}
            if token:
                payload["nextPageToken"] = token
            return FakeResponse(payload=payload)
        message_id = url.rsplit("/", 1)[-1]
        self.fetched.append(message_id)
        return FakeResponse(payload=_raw(message_id, self._bodies.get(message_id, "Update on the role.")))


class RecordingWriter(MailCorpusWriter):
    """A writer that records batches instead of talking to ClickHouse."""

    def __init__(self, existing: set[str] | None = None):
        self.existing = set(existing or ())
        self.batches: list[tuple[list, list]] = []

    def existing_message_ids(self, message_ids):
        return {mid for mid in message_ids if mid in self.existing}

    def write(self, messages, chunks):
        self.batches.append((list(messages), list(chunks)))
        return WriteResult(messages_written=len(messages), chunks_written=len(chunks))


def _plan(**overrides) -> IngestPlan:
    base = dict(query="newer_than:3y", page_size=2)
    base.update(overrides)
    return IngestPlan(**base)


class TestIngest:
    def test_writes_each_page_before_asking_for_the_next(self):
        gmail = ScriptedGmail([(["m1", "m2"], "t2"), (["m3"], None)])
        writer = RecordingWriter()
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer, plan=_plan(),
        )
        assert report.pages == 2
        assert len(writer.batches) == 2
        assert [m.message_id for m in writer.batches[0][0]] == ["m1", "m2"]
        assert report.messages_written == 3

    def test_already_ingested_messages_are_skipped_before_they_are_fetched(self):
        gmail = ScriptedGmail([(["m1", "m2"], None)])
        writer = RecordingWriter(existing={"m1"})
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer, plan=_plan(),
        )
        assert gmail.fetched == ["m2"]
        assert report.messages_skipped == 1
        assert report.messages_fetched == 1

    def test_force_refetches_everything(self):
        gmail = ScriptedGmail([(["m1", "m2"], None)])
        writer = RecordingWriter(existing={"m1", "m2"})
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer,
            plan=_plan(skip_existing=False),
        )
        assert gmail.fetched == ["m1", "m2"]
        assert report.messages_skipped == 0

    def test_rerunning_a_completed_backfill_fetches_nothing(self):
        gmail = ScriptedGmail([(["m1", "m2"], None)])
        writer = RecordingWriter(existing={"m1", "m2"})
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer, plan=_plan(),
        )
        assert gmail.fetched == []
        assert writer.batches == []
        assert report.messages_written == 0
        assert report.messages_skipped == 2

    def test_max_messages_bounds_the_run(self):
        gmail = ScriptedGmail([(["m1", "m2"], "t2"), (["m3", "m4"], None)])
        writer = RecordingWriter()
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer,
            plan=_plan(max_messages=3),
        )
        assert report.messages_fetched == 3
        assert gmail.fetched == ["m1", "m2", "m3"]

    def test_dry_run_writes_nothing_but_still_segments(self):
        gmail = ScriptedGmail([(["m1"], None)])
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=None,
            plan=_plan(dry_run=True),
        )
        assert report.messages_fetched == 1
        assert report.messages_written == 0
        assert report.chunks_written == 0
        assert report.parts["subject"] == 1

    def test_a_writer_is_required_unless_dry_run(self):
        with pytest.raises(ValueError):
            ingest_pages(access_token="tok", http_client=None, writer=None, plan=_plan())

    def test_part_histogram_and_templates_are_reported(self):
        bodies = {
            "m1": "Alice Smith viewed your profile",
            "m2": "Bob Jones viewed your profile",
        }
        gmail = ScriptedGmail([(["m1", "m2"], None)], bodies=bodies)
        writer = RecordingWriter()
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer, plan=_plan(),
        )
        assert report.parts["body"] == 2
        # Both bodies collapse to one template, and "Subject m1"/"Subject m2"
        # collapse to another: four chunks, two templates.
        assert report.chunks_written == 4
        assert len(report.template_ids) == 2

    def test_report_summary_is_counts_only(self):
        gmail = ScriptedGmail([(["m1"], None)])
        writer = RecordingWriter()
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer, plan=_plan(),
        )
        summary = "\n".join(report.summary_lines())
        assert "Update on the role" not in summary
        assert "Subject m1" not in summary
        assert "messages=1" in summary

    def test_fetch_failures_are_collected_not_fatal(self):
        class FlakyGmail(ScriptedGmail):
            def get(self, url, *, params=None, headers=None, timeout=None):
                if url.endswith("/m1"):
                    return FakeResponse(status_code=404)
                return super().get(url, params=params, headers=headers, timeout=timeout)

        gmail = FlakyGmail([(["m1", "m2"], None)])
        writer = RecordingWriter()
        report = ingest_pages(
            access_token="tok", http_client=gmail, writer=writer, plan=_plan(),
            sleep=lambda _s: None,
        )
        assert report.messages_fetched == 1
        assert len(report.errors) == 1

    def test_empty_report_has_no_embeddable_chunks(self):
        assert IngestReport().embeddable_chunks == 0
