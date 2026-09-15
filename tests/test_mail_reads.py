"""Tests for the `mail` corpus read seam.

No live vakr and no populated tables — the ClickHouse client is exercised
against a fake HTTP client, the same injection seam `core/jobsearch_gmail.py`
uses. These tests assert the SQL and the failure modes, which is all this
layer owes the ranker.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.mail_reads import (
    ClickHouseMailCorpus,
    InMemoryMailCorpus,
    MailCorpusUnavailable,
    MailMessage,
    row_to_message,
)


NOW = datetime(2026, 8, 25, 17, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class FakeClickHouseClient:
    """Records the request; replays a canned response."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = responses or []
        self.calls: list[dict] = []

    def post(self, url, *, params, content, timeout):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "sql": content.decode("utf-8"),
                "timeout": timeout,
            }
        )
        if not self.responses:
            return FakeResponse(200, "")
        return self.responses.pop(0)


class ExplodingClient:
    def post(self, *args, **kwargs):
        raise OSError("connection refused")


# --------------------------------------------------------------------------
# in-memory corpus (what the ranker tests run against)
# --------------------------------------------------------------------------


def test_in_memory_corpus_windows_sorts_and_limits():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("m1", "t1", NOW - timedelta(days=1), "a@example.com"),
            MailMessage("m2", "t2", NOW, "b@example.com"),
            MailMessage("m3", "t3", NOW - timedelta(days=40), "c@example.com"),
        ]
    )

    got = corpus.recent_messages(since=NOW - timedelta(days=14), until=NOW)

    assert [m.message_id for m in got] == ["m2", "m1"]
    assert [m.message_id for m in corpus.recent_messages(
        since=NOW - timedelta(days=14), until=NOW, limit=1
    )] == ["m2"]


def test_in_memory_corpus_reply_lookup_is_scoped_and_case_insensitive():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("mine", "t1", NOW, "Nate <NWALKER85@gmail.com>"),
            MailMessage("theirs", "t2", NOW, "other@example.com"),
        ]
    )

    assert corpus.threads_with_message_from(
        ["t1", "t2"], ["nwalker85@gmail.com"]
    ) == frozenset({"t1"})
    # A thread outside the requested scope is never reported.
    assert corpus.threads_with_message_from(["t2"], ["nwalker85@gmail.com"]) == frozenset()


def test_naive_timestamps_are_treated_as_utc():
    message = MailMessage("m", "t", datetime(2026, 8, 25, 17, 0), "a@example.com")
    assert message.ts.tzinfo is timezone.utc


# --------------------------------------------------------------------------
# ClickHouse client
# --------------------------------------------------------------------------


def test_recent_messages_binds_parameters_and_reads_final():
    client = FakeClickHouseClient(
        [
            FakeResponse(
                200,
                '{"message_id":"m1","thread_id":"t1","ts":"2026-08-25 16:00:00.000",'
                '"from_addr":"joe.dontz@parloa.com","from_name":"Joe Dontz",'
                '"to_addrs":["nwalker85@gmail.com"],"cc_addrs":[],'
                '"subject":"Re: Follow-up","labels":["INBOX"],"snippet":"hi"}\n',
            )
        ]
    )
    corpus = ClickHouseMailCorpus(client=client, user="mail_ro", password="x")

    messages = corpus.recent_messages(since=NOW - timedelta(days=14), until=NOW)

    call = client.calls[0]
    assert "FROM messages FINAL" in call["sql"]
    assert "{since:DateTime64(3)}" in call["sql"]
    assert "FORMAT JSONEachRow" in call["sql"]
    # Values are bound, never interpolated into the SQL text.
    assert call["params"]["param_since"] == "2026-08-11 17:00:00.000"
    assert call["params"]["param_until"] == "2026-08-25 17:00:00.000"
    assert call["params"]["database"] == "gmailnwalker85"
    assert call["params"]["user"] == "mail_ro"

    assert len(messages) == 1
    assert messages[0].message_id == "m1"
    assert messages[0].from_addr == "joe.dontz@parloa.com"
    assert messages[0].ts == datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    assert messages[0].labels == ("INBOX",)


def test_threads_with_message_from_binds_arrays_and_short_circuits():
    client = FakeClickHouseClient([FakeResponse(200, '{"thread_id":"t1"}\n')])
    corpus = ClickHouseMailCorpus(client=client)

    got = corpus.threads_with_message_from(["t1", "t2"], ["NWALKER85@gmail.com"])

    assert got == frozenset({"t1"})
    call = client.calls[0]
    assert call["params"]["param_thread_ids"] == "['t1','t2']"
    assert call["params"]["param_addresses"] == "['nwalker85@gmail.com']"

    # Empty scope never issues a query at all.
    assert corpus.threads_with_message_from([], ["a@example.com"]) == frozenset()
    assert corpus.threads_with_message_from(["t1"], []) == frozenset()
    assert len(client.calls) == 1


def test_missing_tables_report_a_named_reason_rather_than_a_generic_failure():
    """The ingest that creates `messages` is in flight. Say so plainly."""
    client = FakeClickHouseClient(
        [FakeResponse(404, "Code: 60. DB::Exception: UNKNOWN_TABLE: messages")]
    )
    corpus = ClickHouseMailCorpus(client=client)

    with pytest.raises(MailCorpusUnavailable) as excinfo:
        corpus.recent_messages(since=NOW - timedelta(days=1), until=NOW)

    assert excinfo.value.reason_code == "mail_corpus_tables_missing"


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (403, "mail_corpus_unauthorized"),
        (500, "mail_corpus_query_failed"),
    ],
)
def test_http_failures_map_to_reason_codes(status, reason):
    corpus = ClickHouseMailCorpus(client=FakeClickHouseClient([FakeResponse(status, "no")]))

    with pytest.raises(MailCorpusUnavailable) as excinfo:
        corpus.recent_messages(since=NOW - timedelta(days=1), until=NOW)

    assert excinfo.value.reason_code == reason


def test_transport_failure_maps_to_unreachable():
    corpus = ClickHouseMailCorpus(client=ExplodingClient())

    with pytest.raises(MailCorpusUnavailable) as excinfo:
        corpus.recent_messages(since=NOW - timedelta(days=1), until=NOW)

    assert excinfo.value.reason_code == "mail_corpus_unreachable"


def test_malformed_rows_are_refused_not_guessed_at():
    corpus = ClickHouseMailCorpus(client=FakeClickHouseClient([FakeResponse(200, "{oops")]))

    with pytest.raises(MailCorpusUnavailable) as excinfo:
        corpus.recent_messages(since=NOW - timedelta(days=1), until=NOW)

    assert excinfo.value.reason_code == "mail_corpus_malformed_response"


def test_no_credentials_are_sent_when_none_are_configured():
    client = FakeClickHouseClient([FakeResponse(200, "")])
    corpus = ClickHouseMailCorpus(client=client)

    corpus.recent_messages(since=NOW - timedelta(days=1), until=NOW)

    assert "user" not in client.calls[0]["params"]
    assert "password" not in client.calls[0]["params"]


def test_from_env_reads_url_and_credentials_from_the_environment():
    corpus = ClickHouseMailCorpus.from_env(
        client=FakeClickHouseClient(),
        environ={
            "MAIL_CLICKHOUSE_URL": "http://vakr.ravenmask.net:8123",
            "MAIL_CLICKHOUSE_USER": "mail_ro",
            "MAIL_CLICKHOUSE_PASSWORD": "from-1password",
        },
    )

    assert corpus._base_url == "http://vakr.ravenmask.net:8123"
    assert corpus._user == "mail_ro"


def test_row_to_message_tolerates_absent_optional_columns():
    message = row_to_message(
        {"message_id": "m", "thread_id": "t", "ts": "2026-08-25 16:00:00.000"}
    )

    assert message.from_addr == ""
    assert message.to_addrs == ()
    assert message.labels == ()


# --------------------------------------------------------------------------
# thread tails — the owed-reply read
# --------------------------------------------------------------------------


def test_in_memory_thread_tails_return_the_last_word_of_each_thread():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("old", "t1", NOW - timedelta(days=200), "them@example.com"),
            MailMessage("newer", "t1", NOW - timedelta(days=150), "them@example.com"),
            MailMessage("solo", "t2", NOW - timedelta(days=2), "them@example.com"),
        ]
    )

    tails = corpus.latest_messages_per_thread(since=NOW - timedelta(days=365), until=NOW)

    assert [m.message_id for m in tails] == ["solo", "newer"]


def test_in_memory_thread_tails_exclude_threads_whose_tail_predates_the_horizon():
    """A thread that died two years ago must not reach the candidate set."""
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("ancient", "t-dead", NOW - timedelta(days=730), "them@example.com"),
            MailMessage("live", "t-live", NOW - timedelta(days=100), "them@example.com"),
        ]
    )

    tails = corpus.latest_messages_per_thread(since=NOW - timedelta(days=365), until=NOW)

    assert [m.message_id for m in tails] == ["live"]


def test_in_memory_thread_tails_ignore_activity_after_the_window_end():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("before", "t1", NOW - timedelta(days=5), "them@example.com"),
            MailMessage("after", "t1", NOW + timedelta(days=5), "them@example.com"),
        ]
    )

    tails = corpus.latest_messages_per_thread(since=NOW - timedelta(days=30), until=NOW)

    assert [m.message_id for m in tails] == ["before"]


def test_clickhouse_thread_tails_use_limit_1_by_thread_id():
    client = FakeClickHouseClient([FakeResponse(200, '{"message_id":"m1","thread_id":"t1","ts":"2026-03-06 15:30:00.000"}\n')])
    corpus = ClickHouseMailCorpus(client=client)

    messages = corpus.latest_messages_per_thread(
        since=NOW - timedelta(days=365), until=NOW, limit=250
    )

    sql = client.calls[0]["sql"]
    assert "FROM messages FINAL" in sql
    assert "ORDER BY ts DESC, message_id DESC" in sql
    assert "LIMIT 1 BY thread_id" in sql
    # `LIMIT n BY cols` must precede the trailing `LIMIT n` in ClickHouse.
    assert sql.index("LIMIT 1 BY thread_id") < sql.index("LIMIT {limit:UInt32}")
    assert client.calls[0]["params"]["param_limit"] == "250"
    assert [m.message_id for m in messages] == ["m1"]


# --------------------------------------------------------------------------
# thread history — the read that makes a debt datable (2026-09-15)
# --------------------------------------------------------------------------


def test_in_memory_thread_messages_returns_every_message_of_the_named_threads_oldest_first():
    corpus = InMemoryMailCorpus(messages=[
        MailMessage(message_id="b", thread_id="t1", ts=NOW - timedelta(days=1), from_addr="x@a.example"),
        MailMessage(message_id="a", thread_id="t1", ts=NOW - timedelta(days=9), from_addr="y@a.example"),
        MailMessage(message_id="c", thread_id="t2", ts=NOW, from_addr="z@a.example"),
    ])
    assert [m.message_id for m in corpus.thread_messages(["t1"])] == ["a", "b"]
    assert corpus.thread_messages([]) == ()


def test_clickhouse_thread_messages_binds_the_thread_ids_as_an_array():
    client = FakeClickHouseClient([FakeResponse(200, '{"message_id":"m1","thread_id":"t1","ts":"2026-08-20 15:30:00.000"}\n')])
    corpus = ClickHouseMailCorpus(client=client)

    messages = corpus.thread_messages(["t2", "t1"])

    sql = client.calls[0]["sql"]
    assert "FROM messages FINAL" in sql
    assert "thread_id IN {thread_ids:Array(String)}" in sql
    assert "ORDER BY ts ASC, message_id ASC" in sql
    assert client.calls[0]["params"]["param_thread_ids"] == "['t1','t2']"
    assert [m.message_id for m in messages] == ["m1"]
    assert corpus.thread_messages([]) == ()
    assert len(client.calls) == 1
