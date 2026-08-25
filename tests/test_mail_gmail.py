"""Gmail full-message fetch — parsing, paging, and retry.

The governed sweep stays metadata-only; this is the private Stage pull that
does need bodies. Auth is reused from core.jobsearch_gmail, not reimplemented.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from core.mail_gmail import (
    DEFAULT_MAIL_CORPUS_QUERY,
    GmailFetchError,
    corpus_query,
    decode_part_data,
    extract_attachment_names,
    extract_body_text,
    fetch_messages,
    html_to_text,
    iter_message_id_pages,
    list_message_ids,
    parse_message,
)


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode().rstrip("=")


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeGmail:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, *, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {})})
        return self._responses.pop(0)


def _raw_message(**overrides):
    base = {
        "id": "18f0",
        "threadId": "18ef",
        "internalDate": "1756045800000",
        "historyId": "99887",
        "labelIds": ["INBOX", "CATEGORY_PERSONAL"],
        "snippet": "Are you free Tuesday?",
        "sizeEstimate": 8421,
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Dana Whitfield <Dana@Acme.Example>"},
                {"name": "To", "value": "Nate <nate@example.com>, other@example.com"},
                {"name": "Cc", "value": "cc@example.com"},
                {"name": "Subject", "value": "Technical screen"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("Hi Nate,\r\n\r\nAre you free Tuesday?\r\n")}},
                {"mimeType": "text/html", "body": {"data": _b64("<p>Hi Nate,</p>")}},
            ],
        },
    }
    base.update(overrides)
    return base


class TestQuery:
    def test_default_window_is_three_years(self):
        assert DEFAULT_MAIL_CORPUS_QUERY == "newer_than:3y"

    def test_query_is_the_whole_mailbox_not_a_relevance_model(self):
        assert corpus_query() == "newer_than:3y"

    def test_before_drives_newest_first_resumption(self):
        checkpoint = datetime(2025, 4, 5, tzinfo=timezone.utc)
        assert corpus_query(before=checkpoint) == "newer_than:3y before:2025/04/05"

    def test_extra_terms_are_appended(self):
        assert corpus_query(years=1, extra="-in:chats") == "newer_than:1y -in:chats"


class TestListing:
    def test_returns_ids_and_the_page_token(self):
        client = FakeGmail([
            FakeResponse(payload={"messages": [{"id": "a"}, {"id": "b"}], "nextPageToken": "t2"})
        ])
        ids, token = list_message_ids(access_token="tok", query="q", client=client)
        assert (ids, token) == (["a", "b"], "t2")
        assert client.calls[0]["headers"]["Authorization"] == "Bearer tok"

    def test_spam_and_trash_are_excluded_unless_asked(self):
        client = FakeGmail([FakeResponse(payload={}), FakeResponse(payload={})])
        list_message_ids(access_token="tok", query="q", client=client)
        assert "includeSpamTrash" not in client.calls[0]["params"]
        list_message_ids(access_token="tok", query="q", client=client, include_spam_trash=True)
        assert client.calls[1]["params"]["includeSpamTrash"] == "true"

    def test_pages_are_walked_newest_first_until_exhausted(self):
        client = FakeGmail([
            FakeResponse(payload={"messages": [{"id": "n1"}], "nextPageToken": "t2"}),
            FakeResponse(payload={"messages": [{"id": "n2"}]}),
        ])
        pages = list(iter_message_id_pages(access_token="tok", query="q", client=client))
        assert pages == [["n1"], ["n2"]]
        assert client.calls[1]["params"]["pageToken"] == "t2"

    def test_max_pages_stops_the_walk(self):
        client = FakeGmail([
            FakeResponse(payload={"messages": [{"id": "n1"}], "nextPageToken": "t2"}),
        ])
        pages = list(iter_message_id_pages(access_token="tok", query="q", client=client, max_pages=1))
        assert pages == [["n1"]]


class TestRetry:
    def test_rate_limit_is_retried_with_backoff(self):
        client = FakeGmail([
            FakeResponse(status_code=429, headers={"Retry-After": "0"}),
            FakeResponse(payload={"messages": [{"id": "a"}]}),
        ])
        slept: list[float] = []
        ids, _ = list_message_ids(
            access_token="tok", query="q", client=client, sleep=slept.append
        )
        assert ids == ["a"]
        assert slept == [1.0]

    def test_client_errors_are_not_retried(self):
        client = FakeGmail([FakeResponse(status_code=403)])
        with pytest.raises(GmailFetchError) as exc:
            list_message_ids(access_token="tok", query="q", client=client, sleep=lambda _s: None)
        assert "403" in str(exc.value)

    def test_retries_are_bounded(self):
        client = FakeGmail([FakeResponse(status_code=503) for _ in range(5)])
        with pytest.raises(GmailFetchError) as exc:
            list_message_ids(access_token="tok", query="q", client=client, sleep=lambda _s: None)
        assert "retries_exhausted" in str(exc.value)


class TestBodyExtraction:
    def test_plaintext_is_preferred_over_html(self):
        text = extract_body_text(_raw_message()["payload"])
        assert text.startswith("Hi Nate,")
        assert "<p>" not in text

    def test_html_is_flattened_when_no_plaintext_part_exists(self):
        payload = {
            "mimeType": "text/html",
            "body": {"data": _b64("<style>p{}</style><p>Hello <b>Nate</b></p><br>Bye")},
        }
        assert extract_body_text(payload) == "Hello Nate\n\nBye"

    def test_attachment_parts_are_not_treated_as_body(self):
        payload = {
            "parts": [
                {"mimeType": "text/plain", "filename": "notes.txt", "body": {"data": _b64("attachment")}},
                {"mimeType": "text/plain", "body": {"data": _b64("real body")}},
            ]
        }
        assert extract_body_text(payload) == "real body"

    def test_html_entities_are_unescaped(self):
        assert html_to_text("<p>a &amp; b</p>") == "a & b"

    def test_malformed_base64_does_not_explode(self):
        assert decode_part_data("!!!not-base64!!!") == ""

    def test_missing_payload_yields_empty_body(self):
        assert extract_body_text(None) == ""

    def test_attachment_names_are_collected_once(self):
        payload = {
            "parts": [
                {"filename": "a.pdf"},
                {"filename": "a.pdf"},
                {"parts": [{"filename": "b.png"}]},
            ]
        }
        assert extract_attachment_names(payload) == ("a.pdf", "b.png")


class TestParse:
    def test_headers_and_metadata_are_flattened(self):
        message = parse_message(_raw_message())
        assert message.message_id == "18f0"
        assert message.thread_id == "18ef"
        assert message.from_addr == "dana@acme.example"
        assert message.from_name == "Dana Whitfield"
        assert message.to_addrs == ("nate@example.com", "other@example.com")
        assert message.cc_addrs == ("cc@example.com",)
        assert message.subject == "Technical screen"
        assert message.labels == ("INBOX", "CATEGORY_PERSONAL")
        assert message.size_estimate == 8421

    def test_internal_date_becomes_a_utc_instant(self):
        message = parse_message(_raw_message())
        assert message.ts == datetime.fromtimestamp(1756045800, tz=timezone.utc)

    def test_missing_internal_date_falls_back_to_epoch(self):
        message = parse_message(_raw_message(internalDate=None))
        assert message.ts.year == 1970

    def test_source_ref_records_provenance(self):
        assert parse_message(_raw_message()).source_ref == "gmail:99887"
        assert parse_message(_raw_message(), source_ref="gmail:backfill").source_ref == "gmail:backfill"

    def test_rfc2047_encoded_subject_is_decoded(self):
        raw = _raw_message()
        raw["payload"]["headers"] = [{"name": "Subject", "value": "=?utf-8?B?w4ZzdGhldGlj?="}]
        assert parse_message(raw).subject == "Æsthetic"

    def test_attachments_set_the_flag(self):
        raw = _raw_message()
        raw["payload"]["parts"].append({"filename": "resume.pdf", "body": {}})
        message = parse_message(raw)
        assert message.has_attachments is True
        assert message.attachment_names == ("resume.pdf",)

    def test_auto_submitted_header_is_carried_for_the_chunker(self):
        raw = _raw_message()
        raw["payload"]["headers"].append({"name": "Auto-Submitted", "value": "auto-replied"})
        assert parse_message(raw).auto_submitted == "auto-replied"

    def test_message_without_an_id_is_refused(self):
        with pytest.raises(GmailFetchError):
            parse_message({"threadId": "x"})


class TestFetchMessages:
    def test_batch_fetch_parses_every_message(self):
        client = FakeGmail([
            FakeResponse(payload=_raw_message(id="a")),
            FakeResponse(payload=_raw_message(id="b")),
        ])
        messages = fetch_messages(["a", "b"], access_token="tok", client=client)
        assert [m.message_id for m in messages] == ["a", "b"]
        assert client.calls[0]["params"]["format"] == "full"

    def test_one_bad_message_does_not_kill_the_backfill(self):
        client = FakeGmail([
            FakeResponse(status_code=404),
            FakeResponse(payload=_raw_message(id="b")),
        ])
        errors: list[str] = []
        messages = fetch_messages(
            ["a", "b"],
            access_token="tok",
            client=client,
            sleep=lambda _s: None,
            on_error=lambda mid, exc: errors.append(mid),
        )
        assert [m.message_id for m in messages] == ["b"]
        assert errors == ["a"]

    def test_without_a_handler_the_error_propagates(self):
        client = FakeGmail([FakeResponse(status_code=404)])
        with pytest.raises(GmailFetchError):
            fetch_messages(["a"], access_token="tok", client=client, sleep=lambda _s: None)
