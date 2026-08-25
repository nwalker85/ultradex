"""ClickHouse Stage for the mail corpus — DDL and an idempotent writer.

Speaks the ClickHouse HTTP interface with ``httpx`` (already a dependency);
no new driver is pulled in for three tables and two INSERTs.

**Access control is deliberately unbaked.** The ClickHouse user, password,
endpoint and database all come from the environment with *no credential
default*, because ``default`` on vakr reaches every database on the host
including ``forensics``. Choosing the user is an operator decision, so this
module refuses to run until one is named.

Authority: ``~/docs/30-projects/career-command-center/DESIGN-mail-corpus-clickhouse.md``.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_CLICKHOUSE_URL = "http://vakr.ravenmask.net:8123"
#: One database per mail account, named ``<provider><account>`` — there will be
#: other addresses and other providers, and they do not share a corpus. Kept to
#: ``[A-Za-z0-9_]`` on purpose: a hyphen would be legal but would force every
#: hand-written query through backticks forever.
DEFAULT_DATABASE = "gmailnwalker85"
DEFAULT_TIMEOUT_SECONDS = 60.0

MESSAGES_TABLE = "messages"
CHUNKS_TABLE = "chunks"
EMBEDDINGS_TABLE = "embeddings"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

#: Sent with every write so ISO-8601 instants (``…Z``) land as true UTC rather
#: than being reinterpreted in the server's local timezone.
INSERT_SETTINGS: dict[str, str] = {"date_time_input_format": "best_effort"}


class ClickHouseError(RuntimeError):
    """A ClickHouse request failed. Carries the server's message, not secrets."""


class MailClickHouseConfigError(RuntimeError):
    """Credential resolution failed. reason_code is safe to log; values are not."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _identifier(name: str, *, what: str) -> str:
    if not _IDENTIFIER_RE.match(name or ""):
        raise MailClickHouseConfigError(f"mail_clickhouse_bad_{what}")
    return name


@dataclass(frozen=True)
class ClickHouseConfig:
    """Everything about *where* and *as whom* — all of it from the environment."""

    url: str = DEFAULT_CLICKHOUSE_URL
    user: str = ""
    password: str = ""
    database: str = DEFAULT_DATABASE
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        _identifier(self.database, what="database")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ClickHouseConfig":
        env = os.environ if environ is None else environ
        user = (env.get("MAIL_CLICKHOUSE_USER") or "").strip()
        if not user:
            raise MailClickHouseConfigError("mail_clickhouse_user_missing")
        password = env.get("MAIL_CLICKHOUSE_PASSWORD")
        if password is None or (
            not password
            and (env.get("MAIL_CLICKHOUSE_ALLOW_EMPTY_PASSWORD") or "") != "1"
        ):
            raise MailClickHouseConfigError("mail_clickhouse_password_missing")
        timeout_raw = (env.get("MAIL_CLICKHOUSE_TIMEOUT") or "").strip()
        try:
            timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT_SECONDS
        except ValueError as exc:
            raise MailClickHouseConfigError("mail_clickhouse_bad_timeout") from exc
        return cls(
            url=(env.get("MAIL_CLICKHOUSE_URL") or DEFAULT_CLICKHOUSE_URL).rstrip("/"),
            user=user,
            password=password,
            database=(env.get("MAIL_CLICKHOUSE_DATABASE") or DEFAULT_DATABASE).strip(),
            timeout=timeout,
        )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "X-ClickHouse-User": self.user,
            "X-ClickHouse-Key": self.password,
        }

    def describe(self) -> str:
        """Safe to print: endpoint, user and database — never the password."""
        return f"{self.url} user={self.user} database={self.database}"


# --- DDL --------------------------------------------------------------------
def schema_statements(database: str = DEFAULT_DATABASE) -> tuple[str, ...]:
    """The three tables from the design, rendered for ``database``.

    ``template_id`` is folded into the ``chunks`` CREATE (the design adds it by
    ALTER); the ALTER is kept as an ``IF NOT EXISTS`` so an already-created
    table converges to the same shape.
    """
    db = _identifier(database, what="database")
    return (
        f"CREATE DATABASE IF NOT EXISTS {db}",
        f"""CREATE TABLE IF NOT EXISTS {db}.{MESSAGES_TABLE}
(
    message_id        String,
    thread_id         String,
    ts                DateTime64(3),
    from_addr         String,
    from_name         String,
    to_addrs          Array(String),
    cc_addrs          Array(String),
    subject           String,
    labels            Array(LowCardinality(String)),
    snippet           String,
    body_text         String,
    has_attachments   Bool,
    attachment_names  Array(String),
    size_estimate     UInt32,
    source_ref        String,
    ingested_at       DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (thread_id, ts, message_id)
TTL toDateTime(ts) + INTERVAL 3 YEAR""",
        f"""CREATE TABLE IF NOT EXISTS {db}.{CHUNKS_TABLE}
(
    message_id   String,
    thread_id    String,
    ts           DateTime64(3),
    seq          UInt32,
    part         LowCardinality(String),
    text         String,
    char_len     UInt32,
    template_id  String DEFAULT '',
    ingested_at  DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (message_id, seq)
TTL toDateTime(ts) + INTERVAL 3 YEAR""",
        f"ALTER TABLE {db}.{CHUNKS_TABLE} ADD COLUMN IF NOT EXISTS template_id String DEFAULT ''",
        f"""CREATE TABLE IF NOT EXISTS {db}.{EMBEDDINGS_TABLE}
(
    corpus      LowCardinality(String),
    doc_id      String,
    seq         UInt32,
    ts          DateTime64(3),
    role        LowCardinality(String),
    text        String,
    embedding   Array(Float32),
    model       LowCardinality(String),
    ingested_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (corpus, doc_id, seq, model)""",
    )


# --- row shaping ------------------------------------------------------------
def format_datetime(moment: datetime) -> str:
    """ISO-8601 in UTC with millisecond precision, for ``best_effort`` parsing."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def message_row(message: Any) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "thread_id": message.thread_id,
        "ts": format_datetime(message.ts),
        "from_addr": message.from_addr,
        "from_name": message.from_name,
        "to_addrs": list(message.to_addrs),
        "cc_addrs": list(message.cc_addrs),
        "subject": message.subject,
        "labels": list(message.labels),
        "snippet": message.snippet,
        "body_text": message.body_text,
        "has_attachments": bool(message.has_attachments),
        "attachment_names": list(message.attachment_names),
        "size_estimate": int(message.size_estimate),
        "source_ref": message.source_ref,
    }


def chunk_row(chunk: Any) -> dict[str, Any]:
    return {
        "message_id": chunk.message_id,
        "thread_id": chunk.thread_id,
        "ts": format_datetime(chunk.ts),
        "seq": int(chunk.seq),
        "part": chunk.part,
        "text": chunk.text,
        "char_len": int(chunk.char_len),
        "template_id": chunk.template_id,
    }


def to_json_each_row(rows: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(
        json.dumps(row, separators=(",", ":"), ensure_ascii=False) for row in rows
    )


# --- client -----------------------------------------------------------------
class MailClickHouseClient:
    """Thin HTTP client. The caller owns the ``httpx.Client`` lifecycle."""

    def __init__(self, *, config: ClickHouseConfig, client) -> None:
        self._config = config
        self._client = client

    @property
    def config(self) -> ClickHouseConfig:
        return self._config

    @property
    def database(self) -> str:
        return self._config.database

    def _post(self, *, sql: str, body: str | None = None, settings: Mapping[str, str] | None = None) -> str:
        params: dict[str, str] = {"query": sql}
        params.update(settings or {})
        response = self._client.post(
            f"{self._config.url}/",
            params=params,
            content=(body or "").encode("utf-8"),
            headers={**self._config.headers, "Content-Type": "text/plain; charset=utf-8"},
            timeout=self._config.timeout,
        )
        if response.status_code >= 400:
            raise ClickHouseError(
                f"clickhouse HTTP {response.status_code}: {response.text[:500]}"
            )
        return response.text

    def command(self, sql: str) -> str:
        """Run a statement that returns no rows (DDL, ALTER, OPTIMIZE)."""
        return self._post(sql=sql)

    def query_rows(self, sql: str) -> list[dict[str, Any]]:
        """Run a SELECT and decode ``JSONEachRow``."""
        text = self._post(sql=f"{sql} FORMAT JSONEachRow")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def query_scalar(self, sql: str) -> Any:
        rows = self.query_rows(sql)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    def insert_rows(self, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
        """Append rows. ReplacingMergeTree collapses exact re-runs at merge."""
        if not rows:
            return 0
        name = _identifier(table, what="table")
        sql = f"INSERT INTO {self.database}.{name} FORMAT JSONEachRow"
        self._post(sql=sql, body=to_json_each_row(rows), settings=INSERT_SETTINGS)
        return len(rows)

    def apply_schema(self) -> list[str]:
        """Create database + tables. Idempotent; safe to run on every start."""
        applied: list[str] = []
        for statement in schema_statements(self.database):
            self.command(statement)
            applied.append(statement.split("\n", 1)[0].strip())
        return applied

    def table_exists(self, table: str) -> bool:
        name = _identifier(table, what="table")
        rows = self.query_rows(
            "SELECT count() AS n FROM system.tables "
            f"WHERE database = '{self.database}' AND name = '{name}'"
        )
        return bool(rows) and int(rows[0]["n"]) > 0


@dataclass(frozen=True)
class WriteResult:
    """What one batch actually did — the numbers a backfill log needs."""

    messages_written: int = 0
    chunks_written: int = 0
    messages_skipped: int = 0

    def merged(self, other: "WriteResult") -> "WriteResult":
        return WriteResult(
            messages_written=self.messages_written + other.messages_written,
            chunks_written=self.chunks_written + other.chunks_written,
            messages_skipped=self.messages_skipped + other.messages_skipped,
        )


class MailCorpusWriter:
    """Idempotent writer for ``mail.messages`` + ``mail.chunks``.

    ReplacingMergeTree collapses duplicates at merge time, but a re-run should
    also be *cheap*: ``existing_message_ids`` lets the caller skip work it has
    already done rather than re-fetching and re-writing it.
    """

    def __init__(self, client: MailClickHouseClient) -> None:
        self._client = client

    @property
    def client(self) -> MailClickHouseClient:
        return self._client

    def existing_message_ids(self, message_ids: Sequence[str]) -> set[str]:
        candidates = [mid for mid in message_ids if _MESSAGE_ID_RE.match(mid or "")]
        if not candidates:
            return set()
        in_list = ",".join(f"'{mid}'" for mid in sorted(set(candidates)))
        rows = self._client.query_rows(
            f"SELECT DISTINCT message_id FROM {self._client.database}.{MESSAGES_TABLE} "
            f"WHERE message_id IN ({in_list})"
        )
        return {str(row["message_id"]) for row in rows}

    def write(self, messages: Sequence[Any], chunks: Sequence[Any]) -> WriteResult:
        written = self._client.insert_rows(
            MESSAGES_TABLE, [message_row(message) for message in messages]
        )
        chunk_count = self._client.insert_rows(
            CHUNKS_TABLE, [chunk_row(chunk) for chunk in chunks]
        )
        return WriteResult(messages_written=written, chunks_written=chunk_count)

    def oldest_ingested_ts(self) -> datetime | None:
        """Backfill checkpoint: how far back the newest-first pull has reached."""
        value = self._client.query_scalar(
            f"SELECT min(ts) AS oldest FROM {self._client.database}.{MESSAGES_TABLE}"
        )
        if not value or str(value).startswith("1970-01-01"):
            return None
        text = str(value).replace("T", " ").rstrip("Z")
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def corpus_counts(self) -> dict[str, int]:
        db = self._client.database
        rows = self._client.query_rows(
            f"SELECT (SELECT count() FROM {db}.{MESSAGES_TABLE} FINAL) AS messages, "
            f"(SELECT count() FROM {db}.{CHUNKS_TABLE} FINAL) AS chunks"
        )
        if not rows:
            return {"messages": 0, "chunks": 0}
        return {key: int(value) for key, value in rows[0].items()}
