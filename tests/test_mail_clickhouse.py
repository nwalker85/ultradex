"""ClickHouse Stage — DDL shape, credential refusal, and idempotent writes."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from core.mail_clickhouse import (
    CHUNKS_TABLE,
    DEFAULT_CLICKHOUSE_URL,
    DEFAULT_DATABASE,
    MESSAGES_TABLE,
    ClickHouseConfig,
    ClickHouseError,
    MailClickHouseClient,
    MailClickHouseConfigError,
    MailCorpusWriter,
    WriteResult,
    chunk_row,
    format_datetime,
    message_row,
    schema_statements,
    to_json_each_row,
)
from core.mail_corpus import MailMessage, segment_message

TS = datetime(2026, 8, 24, 14, 30, 0, 250000, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.headers: dict[str, str] = {}


class FakeHttpClient:
    """Records ClickHouse HTTP calls and replays scripted responses."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.calls: list[dict] = []
        self._responses = list(responses or [])

    def post(self, url, *, params=None, content=None, headers=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "params": dict(params or {}),
                "body": (content or b"").decode("utf-8"),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse()

    @property
    def queries(self) -> list[str]:
        return [call["params"]["query"] for call in self.calls]


def _config(**overrides) -> ClickHouseConfig:
    base = dict(url="http://ch.example:8123", user="mail_ingest", password="s3cr3t")
    base.update(overrides)
    return ClickHouseConfig(**base)


def _message(**overrides) -> MailMessage:
    base = dict(
        message_id="msg-1",
        thread_id="thr-1",
        ts=TS,
        from_addr="dana@acme.example",
        from_name="Dana Whitfield",
        to_addrs=("nate@example.com",),
        cc_addrs=(),
        subject="Technical screen",
        labels=("INBOX", "IMPORTANT"),
        snippet="Are you free Tuesday?",
        body_text="Hi Nate,\n\nAre you free Tuesday?\n",
        has_attachments=False,
        attachment_names=(),
        size_estimate=4096,
        source_ref="gmail:12345",
    )
    base.update(overrides)
    return MailMessage(**base)


class TestConfig:
    def test_user_is_required_there_is_no_default(self, monkeypatch):
        with pytest.raises(MailClickHouseConfigError) as exc:
            ClickHouseConfig.from_env({})
        assert exc.value.reason_code == "mail_clickhouse_user_missing"

    def test_password_is_required(self):
        with pytest.raises(MailClickHouseConfigError) as exc:
            ClickHouseConfig.from_env({"MAIL_CLICKHOUSE_USER": "mail_ingest"})
        assert exc.value.reason_code == "mail_clickhouse_password_missing"

    def test_empty_password_requires_an_explicit_opt_in(self):
        env = {"MAIL_CLICKHOUSE_USER": "mail_ingest", "MAIL_CLICKHOUSE_PASSWORD": ""}
        with pytest.raises(MailClickHouseConfigError):
            ClickHouseConfig.from_env(env)
        config = ClickHouseConfig.from_env(
            env | {"MAIL_CLICKHOUSE_ALLOW_EMPTY_PASSWORD": "1"}
        )
        assert config.password == ""

    def test_endpoint_and_database_default_but_credentials_do_not(self):
        config = ClickHouseConfig.from_env(
            {"MAIL_CLICKHOUSE_USER": "mail_ingest", "MAIL_CLICKHOUSE_PASSWORD": "x"}
        )
        assert config.url == DEFAULT_CLICKHOUSE_URL
        # Pinned deliberately: one database per mail account, named
        # <provider><account>. Other addresses and providers get their own.
        assert config.database == "gmailnwalker85"
        # No hyphen, so no statement anywhere needs backtick quoting.
        assert "-" not in config.database

    def test_everything_is_overridable_from_env(self):
        config = ClickHouseConfig.from_env(
            {
                "MAIL_CLICKHOUSE_URL": "http://other:8123/",
                "MAIL_CLICKHOUSE_USER": "corpus",
                "MAIL_CLICKHOUSE_PASSWORD": "pw",
                "MAIL_CLICKHOUSE_DATABASE": "mail_dev",
                "MAIL_CLICKHOUSE_TIMEOUT": "12.5",
            }
        )
        assert (config.url, config.user, config.database, config.timeout) == (
            "http://other:8123", "corpus", "mail_dev", 12.5,
        )

    def test_bad_database_name_is_refused(self):
        with pytest.raises(MailClickHouseConfigError):
            ClickHouseConfig(user="u", password="p", database="mail; DROP DATABASE x")

    def test_describe_never_leaks_the_password(self):
        assert "s3cr3t" not in _config().describe()

    def test_credentials_travel_as_headers_not_query_params(self):
        assert _config().headers == {
            "X-ClickHouse-User": "mail_ingest",
            "X-ClickHouse-Key": "s3cr3t",
        }


class TestSchema:
    def test_three_tables_plus_database_and_template_alter(self):
        db = DEFAULT_DATABASE
        statements = schema_statements(db)
        joined = "\n".join(statements)
        assert f"CREATE DATABASE IF NOT EXISTS {db}" in joined
        assert f"{db}.messages" in joined
        assert f"{db}.chunks" in joined
        assert f"{db}.embeddings" in joined
        assert "ADD COLUMN IF NOT EXISTS template_id" in joined

    def test_replacing_merge_tree_on_every_table(self):
        creates = [s for s in schema_statements() if s.startswith("CREATE TABLE")]
        assert len(creates) == 3
        assert all("ReplacingMergeTree(ingested_at)" in s for s in creates)

    def test_dedup_keys_match_the_design(self):
        joined = "\n".join(schema_statements())
        assert "ORDER BY (thread_id, ts, message_id)" in joined
        assert "ORDER BY (message_id, seq)" in joined
        assert "ORDER BY (corpus, doc_id, seq, model)" in joined

    def test_three_year_ttl_on_corpus_tables(self):
        joined = "\n".join(schema_statements())
        assert joined.count("TTL toDateTime(ts) + INTERVAL 3 YEAR") == 2

    def test_embeddings_mirror_the_forensics_column_shape(self):
        embeddings = [s for s in schema_statements() if ".embeddings" in s][0]
        for column in ("corpus", "doc_id", "seq", "ts", "role", "text", "embedding"):
            assert column in embeddings

    def test_database_name_is_templated(self):
        assert "mail_dev.messages" in "\n".join(schema_statements("mail_dev"))

    def test_injection_in_the_database_name_is_refused(self):
        with pytest.raises(MailClickHouseConfigError):
            schema_statements("mail; DROP TABLE x")


class TestRowShaping:
    def test_timestamps_are_utc_iso_with_millis(self):
        assert format_datetime(TS) == "2026-08-24T14:30:00.250Z"

    def test_naive_timestamps_are_treated_as_utc(self):
        assert format_datetime(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05.000Z"

    def test_message_row_matches_the_table_columns(self):
        row = message_row(_message())
        assert set(row) == {
            "message_id", "thread_id", "ts", "from_addr", "from_name",
            "to_addrs", "cc_addrs", "subject", "labels", "snippet",
            "body_text", "has_attachments", "attachment_names",
            "size_estimate", "source_ref",
        }
        assert row["labels"] == ["INBOX", "IMPORTANT"]
        assert row["has_attachments"] is False

    def test_ingested_at_is_left_to_the_server_default(self):
        assert "ingested_at" not in message_row(_message())
        assert "ingested_at" not in chunk_row(segment_message(_message())[0])

    def test_chunk_row_carries_the_template_id(self):
        row = chunk_row(segment_message(_message())[0])
        assert set(row) == {
            "message_id", "thread_id", "ts", "seq", "part",
            "text", "char_len", "template_id",
        }

    def test_json_each_row_is_newline_delimited(self):
        text = to_json_each_row([{"a": 1}, {"a": 2}])
        assert [json.loads(line) for line in text.splitlines()] == [{"a": 1}, {"a": 2}]

    def test_unicode_survives_without_escaping(self):
        assert "naïve" in to_json_each_row([{"subject": "naïve"}])


class TestClient:
    def test_insert_uses_json_each_row_and_best_effort_datetimes(self):
        http = FakeHttpClient()
        client = MailClickHouseClient(config=_config(), client=http)
        written = client.insert_rows(MESSAGES_TABLE, [message_row(_message())])
        assert written == 1
        call = http.calls[0]
        assert call["params"]["query"] == f"INSERT INTO {DEFAULT_DATABASE}.messages FORMAT JSONEachRow"
        assert call["params"]["date_time_input_format"] == "best_effort"
        assert json.loads(call["body"])["message_id"] == "msg-1"

    def test_empty_insert_is_a_no_op(self):
        http = FakeHttpClient()
        client = MailClickHouseClient(config=_config(), client=http)
        assert client.insert_rows(MESSAGES_TABLE, []) == 0
        assert http.calls == []

    def test_bad_table_name_is_refused(self):
        client = MailClickHouseClient(config=_config(), client=FakeHttpClient())
        with pytest.raises(MailClickHouseConfigError):
            client.insert_rows("messages; DROP TABLE other.messages", [{"a": 1}])

    def test_http_error_is_surfaced(self):
        http = FakeHttpClient([FakeResponse(status_code=516, text="AUTHENTICATION_FAILED")])
        client = MailClickHouseClient(config=_config(), client=http)
        with pytest.raises(ClickHouseError) as exc:
            client.command("SELECT 1")
        assert "516" in str(exc.value)

    def test_apply_schema_runs_every_statement(self):
        http = FakeHttpClient()
        client = MailClickHouseClient(config=_config(), client=http)
        applied = client.apply_schema()
        assert len(applied) == len(schema_statements(DEFAULT_DATABASE))
        assert len(http.calls) == len(applied)

    def test_apply_schema_is_idempotent_by_construction(self):
        joined = "\n".join(schema_statements())
        assert joined.count("IF NOT EXISTS") >= 4

    def test_query_rows_decodes_json_each_row(self):
        http = FakeHttpClient([FakeResponse(text='{"n":2}\n{"n":3}\n')])
        client = MailClickHouseClient(config=_config(), client=http)
        assert client.query_rows("SELECT n FROM t") == [{"n": 2}, {"n": 3}]
        assert http.queries[0].endswith("FORMAT JSONEachRow")


class TestWriter:
    def test_existing_ids_are_reported_so_a_rerun_is_cheap(self):
        http = FakeHttpClient([FakeResponse(text='{"message_id":"msg-1"}\n')])
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        assert writer.existing_message_ids(["msg-1", "msg-2"]) == {"msg-1"}
        assert "IN ('msg-1','msg-2')" in http.queries[0]

    def test_ids_with_quotes_are_dropped_not_interpolated(self):
        http = FakeHttpClient([FakeResponse(text="")])
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        writer.existing_message_ids(["msg-1", "x' OR 1=1 --"])
        assert "OR 1=1" not in http.queries[0]

    def test_no_valid_ids_means_no_query(self):
        http = FakeHttpClient()
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        assert writer.existing_message_ids([]) == set()
        assert http.calls == []

    def test_write_inserts_messages_then_chunks(self):
        http = FakeHttpClient()
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        message = _message()
        chunks = segment_message(message)
        result = writer.write([message], chunks)
        assert result.messages_written == 1
        assert result.chunks_written == len(chunks)
        assert http.queries == [
            f"INSERT INTO {DEFAULT_DATABASE}.{MESSAGES_TABLE} FORMAT JSONEachRow",
            f"INSERT INTO {DEFAULT_DATABASE}.{CHUNKS_TABLE} FORMAT JSONEachRow",
        ]

    def test_rewriting_the_same_message_produces_identical_dedup_keys(self):
        message = _message()
        first = [message_row(message)] + [chunk_row(c) for c in segment_message(message)]
        second = [message_row(message)] + [chunk_row(c) for c in segment_message(message)]
        assert first == second

    def test_oldest_ingested_ts_parses_a_checkpoint(self):
        http = FakeHttpClient([FakeResponse(text='{"oldest":"2024-03-04 05:06:07.000"}\n')])
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        checkpoint = writer.oldest_ingested_ts()
        assert checkpoint == datetime(2024, 3, 4, 5, 6, 7, tzinfo=timezone.utc)

    def test_empty_corpus_has_no_checkpoint(self):
        http = FakeHttpClient([FakeResponse(text='{"oldest":"1970-01-01 00:00:00.000"}\n')])
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        assert writer.oldest_ingested_ts() is None

    def test_corpus_counts_uses_final_for_a_collapsed_view(self):
        http = FakeHttpClient([FakeResponse(text='{"messages":10,"chunks":42}\n')])
        writer = MailCorpusWriter(MailClickHouseClient(config=_config(), client=http))
        assert writer.corpus_counts() == {"messages": 10, "chunks": 42}
        assert "FINAL" in http.queries[0]

    def test_write_results_merge(self):
        merged = WriteResult(1, 2, 3).merged(WriteResult(4, 5, 6))
        assert (merged.messages_written, merged.chunks_written, merged.messages_skipped) == (5, 7, 9)
