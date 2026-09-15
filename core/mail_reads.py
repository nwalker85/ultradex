"""Read side of the private mail corpus (ClickHouse): the three reads the ranker needs.

Landed from feat/mail-stupid-ranker as its own module because `core/mail_corpus.py`
on main is the write/segmentation side and the two had collided on the filename.

Thin read interface over the `mail` corpus (AAL Sense Stage).

This module is *only* the data-access seam for the surfacing layer. It owns no
relevance logic — see `core/mail_ranking.py` for that. It exists so the ranker
can be written, tested, and reviewed before `<database>.messages` is populated: the
`MailCorpus` protocol has an in-memory implementation for fixtures and a thin
ClickHouse implementation for the real table.

Schema authority: `~/docs/30-projects/career-command-center/DESIGN-mail-corpus-clickhouse.md`
(`<database>.messages` on ClickHouse at `vakr.ravenmask.net:8123`). The DDL and the
ingest that fills it are **not** this module's business and are being built
concurrently; nothing here creates or writes anything.

`MailMessage` deliberately does not carry `body_text`. The ranker's whole rule
is recency × known-sender × replied-thread — none of it reads prose. Keeping
bodies out of the projection keeps the surfacing path clear of the Vór
boundary that governed evidence lives behind: what is ranked is metadata, and
promotion of anything more goes through Consent.

Credentials: `MAIL_CLICKHOUSE_USER` / `MAIL_CLICKHOUSE_PASSWORD` are read from
the environment only. Populate them from 1Password at run time, e.g.
`op://ravenmask/vakr-clickhouse-mail/username` and
`op://ravenmask/vakr-clickhouse-mail/password`. No credential is defaulted here
and none is ever written to the tree. The design doc's open question #1 (a
`mail`-scoped ClickHouse user rather than `default`) is still open — this
client will use whatever principal it is handed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import AbstractSet, Protocol


DEFAULT_CLICKHOUSE_URL = "http://vakr.ravenmask.net:8123"
DEFAULT_DATABASE = "gmailnwalker85"  # one database per mail account, matching core.mail_clickhouse
DEFAULT_FETCH_LIMIT = 500


class MailCorpusUnavailable(Exception):
    """The corpus could not be read. `reason_code` is safe to log; values are not."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class MailMessage:
    """One row of `<database>.messages`, minus the body.

    Field names mirror the design doc's column names exactly so that a schema
    change shows up here as a rename rather than as silent drift.
    """

    message_id: str
    thread_id: str
    ts: datetime
    from_addr: str
    from_name: str = ""
    to_addrs: tuple[str, ...] = ()
    cc_addrs: tuple[str, ...] = ()
    subject: str = ""
    labels: tuple[str, ...] = ()
    snippet: str = ""

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            object.__setattr__(self, "ts", self.ts.replace(tzinfo=timezone.utc))


class MailCorpus(Protocol):
    """The three reads the ranker needs. Nothing else.

    `recent_messages` answers "what arrived"; `latest_messages_per_thread`
    answers "whose was the last word in each thread", which is the only way to
    see a reply the operator owes — an owed reply is defined by nothing having
    happened since. `threads_with_message_from` answers "have I ever spoken
    here".
    """

    def recent_messages(
        self,
        *,
        since: datetime,
        until: datetime,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Sequence[MailMessage]:
        """Messages with `since <= ts <= until`, newest first."""

    def latest_messages_per_thread(
        self,
        *,
        since: datetime,
        until: datetime,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Sequence[MailMessage]:
        """The newest message of every thread whose newest message is in range.

        This is the owed-reply read. An owed reply is defined by the *absence*
        of anything after it, so the question is never "what arrived" but "what
        is each thread's last word, and whose was it". Threads whose tail falls
        outside the range are absent entirely, which is what bounds the sweep.
        """

    def thread_messages(self, thread_ids: Sequence[str]) -> Sequence[MailMessage]:
        """Every message of the named threads, oldest first.

        The read that dates a debt and names who a thread is with. Independent
        of the arrival window and its row cap on purpose: an owed thread's
        earlier messages are exactly the ones a newest-first cap drops.
        """

    def threads_with_message_from(
        self,
        thread_ids: Sequence[str],
        addresses: Sequence[str],
    ) -> AbstractSet[str]:
        """Subset of `thread_ids` containing at least one message from `addresses`.

        This is how "you replied to this thread" is answered: the operator's own
        addresses appear as `from_addr` on the messages they sent. Whole-thread
        scope on purpose — a reply anywhere in the thread counts, including one
        sent before the message being ranked arrived.
        """


def normalize_address(raw: str | None) -> str:
    """`"Joe Dontz <Joe.Dontz@Parloa.com>"` -> `"joe.dontz@parloa.com"`.

    Lowercase, trimmed, angle-brackets unwrapped. Deliberately does **not**
    strip `+tags` or dots: those are provider-specific identity rules, and
    collapsing them would silently merge addresses the operator may consider
    distinct. If that turns out to matter it is a decision, not a default.
    """
    if not raw:
        return ""
    value = raw.strip()
    if "<" in value and ">" in value:
        value = value[value.rindex("<") + 1 : value.index(">", value.rindex("<"))]
    return value.strip().strip("'\"").lower()


@dataclass
class InMemoryMailCorpus:
    """Fixture-backed corpus. The implementation tests run against."""

    messages: list[MailMessage] = field(default_factory=list)

    def recent_messages(
        self,
        *,
        since: datetime,
        until: datetime,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Sequence[MailMessage]:
        window = [
            message for message in self.messages if since <= message.ts <= until
        ]
        window.sort(key=lambda m: (m.ts, m.message_id), reverse=True)
        return tuple(window[:limit])

    def latest_messages_per_thread(
        self,
        *,
        since: datetime,
        until: datetime,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Sequence[MailMessage]:
        tails: dict[str, MailMessage] = {}
        for message in self.messages:
            if message.ts > until:
                continue
            current = tails.get(message.thread_id)
            if current is None or (message.ts, message.message_id) > (
                current.ts,
                current.message_id,
            ):
                tails[message.thread_id] = message
        ordered = [message for message in tails.values() if message.ts >= since]
        ordered.sort(key=lambda m: (m.ts, m.message_id), reverse=True)
        return tuple(ordered[:limit])

    def thread_messages(self, thread_ids: Sequence[str]) -> Sequence[MailMessage]:
        scope = {tid for tid in thread_ids if tid}
        if not scope:
            return ()
        rows = [m for m in self.messages if m.thread_id in scope]
        rows.sort(key=lambda m: (m.ts, m.message_id))
        return tuple(rows)

    def threads_with_message_from(
        self,
        thread_ids: Sequence[str],
        addresses: Sequence[str],
    ) -> AbstractSet[str]:
        wanted = {normalize_address(address) for address in addresses} - {""}
        scope = set(thread_ids)
        return frozenset(
            message.thread_id
            for message in self.messages
            if message.thread_id in scope
            and normalize_address(message.from_addr) in wanted
        )


def _clickhouse_array_literal(values: Iterable[str]) -> str:
    """ClickHouse HTTP array parameter literal: `['a','b']`."""
    return "[" + ",".join("'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'" for v in values) + "]"


def _parse_ts(raw: object) -> datetime:
    text = str(raw).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_tuple(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,) if raw else ()
    return tuple(str(item) for item in raw)


def row_to_message(row: Mapping[str, object]) -> MailMessage:
    """Map one `JSONEachRow` row of `<database>.messages` onto `MailMessage`."""
    return MailMessage(
        message_id=str(row["message_id"]),
        thread_id=str(row["thread_id"]),
        ts=_parse_ts(row["ts_text"] if "ts_text" in row else row["ts"]),
        from_addr=str(row.get("from_addr") or ""),
        from_name=str(row.get("from_name") or ""),
        to_addrs=_as_tuple(row.get("to_addrs")),
        cc_addrs=_as_tuple(row.get("cc_addrs")),
        subject=str(row.get("subject") or ""),
        labels=_as_tuple(row.get("labels")),
        snippet=str(row.get("snippet") or ""),
    )


class ClickHouseMailCorpus:
    """`MailCorpus` over the ClickHouse HTTP interface.

    `client` is any object with a `requests`/`httpx`-shaped `post` — injected
    rather than constructed, the same seam `core/jobsearch_gmail.py` uses, so
    tests never need a live vakr and a live run never needs a test double.

    Queries read `FROM messages FINAL`: the table is a ReplacingMergeTree,
    so before a merge the same `message_id` can be present more than once, and
    a duplicate row would double-count nothing here but would waste a rank slot
    and show the operator the same mail twice.

    SQL is parameterised via ClickHouse's `param_*` HTTP parameters, not string
    interpolation — thread IDs and addresses reach the server as bound values.
    """

    def __init__(
        self,
        *,
        client,
        base_url: str = DEFAULT_CLICKHOUSE_URL,
        database: str = DEFAULT_DATABASE,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._database = database
        self._user = user
        self._password = password
        self._timeout = timeout

    @classmethod
    def from_env(cls, *, client, environ: Mapping[str, str]):
        return cls(
            client=client,
            base_url=(environ.get("MAIL_CLICKHOUSE_URL") or DEFAULT_CLICKHOUSE_URL),
            database=(environ.get("MAIL_CLICKHOUSE_DATABASE") or DEFAULT_DATABASE),
            user=(environ.get("MAIL_CLICKHOUSE_USER") or None),
            password=(environ.get("MAIL_CLICKHOUSE_PASSWORD") or None),
        )

    def _query(self, sql: str, params: Mapping[str, str]) -> list[dict]:
        request_params: dict[str, str] = {"database": self._database}
        if self._user is not None:
            request_params["user"] = self._user
        if self._password is not None:
            request_params["password"] = self._password
        for name, value in params.items():
            request_params[f"param_{name}"] = value

        try:
            response = self._client.post(
                self._base_url + "/",
                params=request_params,
                content=sql.encode("utf-8"),
                timeout=self._timeout,
            )
        except TypeError:
            # A wrong-shaped injected client is a programming error here, not a
            # sick corpus — never launder it into "unreachable".
            raise
        except Exception as exc:  # transport-level: host down, DNS, TLS, timeout
            raise MailCorpusUnavailable("mail_corpus_unreachable") from exc

        status = getattr(response, "status_code", 200)
        text = getattr(response, "text", "") or ""
        if status != 200:
            # Code 60 = UNKNOWN_TABLE. The corpus tables are built by the ingest
            # work in flight; say so plainly instead of reporting a generic 500.
            if "UNKNOWN_TABLE" in text or "Code: 60" in text:
                raise MailCorpusUnavailable("mail_corpus_tables_missing")
            if status in (401, 403):
                raise MailCorpusUnavailable("mail_corpus_unauthorized")
            raise MailCorpusUnavailable("mail_corpus_query_failed")

        rows: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise MailCorpusUnavailable("mail_corpus_malformed_response") from exc
        return rows

    def recent_messages(
        self,
        *,
        since: datetime,
        until: datetime,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Sequence[MailMessage]:
        sql = (
            "SELECT message_id, thread_id, toString(ts) AS ts_text, from_addr, from_name, "
            "to_addrs, cc_addrs, subject, labels, snippet "
            "FROM messages FINAL "
            "WHERE ts >= {since:DateTime64(3)} AND ts <= {until:DateTime64(3)} "
            "ORDER BY ts DESC, message_id DESC "
            "LIMIT {limit:UInt32} "
            "FORMAT JSONEachRow"
        )
        rows = self._query(
            sql,
            {
                "since": _clickhouse_datetime(since),
                "until": _clickhouse_datetime(until),
                "limit": str(int(limit)),
            },
        )
        return tuple(row_to_message(row) for row in rows)

    def latest_messages_per_thread(
        self,
        *,
        since: datetime,
        until: datetime,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Sequence[MailMessage]:
        # `LIMIT 1 BY thread_id` after `ORDER BY ts DESC` keeps the newest row
        # per thread; the trailing `LIMIT` then truncates by recency rather
        # than by thread id. A thread whose tail predates `since` never appears,
        # which is what bounds the owed-reply horizon at the server.
        sql = (
            "SELECT message_id, thread_id, toString(ts) AS ts_text, from_addr, from_name, "
            "to_addrs, cc_addrs, subject, labels, snippet "
            "FROM messages FINAL "
            "WHERE ts >= {since:DateTime64(3)} AND ts <= {until:DateTime64(3)} "
            "ORDER BY ts DESC, message_id DESC "
            "LIMIT 1 BY thread_id "
            "LIMIT {limit:UInt32} "
            "FORMAT JSONEachRow"
        )
        rows = self._query(
            sql,
            {
                "since": _clickhouse_datetime(since),
                "until": _clickhouse_datetime(until),
                "limit": str(int(limit)),
            },
        )
        return tuple(row_to_message(row) for row in rows)

    def thread_messages(self, thread_ids: Sequence[str]) -> Sequence[MailMessage]:
        scope = sorted({tid for tid in thread_ids if tid})
        if not scope:
            return ()
        sql = (
            "SELECT message_id, thread_id, toString(ts) AS ts_text, from_addr, from_name, "
            "to_addrs, cc_addrs, subject, labels, snippet "
            "FROM messages FINAL "
            "WHERE thread_id IN {thread_ids:Array(String)} "
            "ORDER BY ts ASC, message_id ASC "
            "FORMAT JSONEachRow"
        )
        rows = self._query(sql, {"thread_ids": _clickhouse_array_literal(scope)})
        return tuple(row_to_message(row) for row in rows)

    def threads_with_message_from(
        self,
        thread_ids: Sequence[str],
        addresses: Sequence[str],
    ) -> AbstractSet[str]:
        scope = sorted({tid for tid in thread_ids if tid})
        wanted = sorted({normalize_address(a) for a in addresses} - {""})
        if not scope or not wanted:
            return frozenset()
        sql = (
            "SELECT DISTINCT thread_id FROM messages FINAL "
            "WHERE thread_id IN {thread_ids:Array(String)} "
            "AND lower(from_addr) IN {addresses:Array(String)} "
            "FORMAT JSONEachRow"
        )
        rows = self._query(
            sql,
            {
                "thread_ids": _clickhouse_array_literal(scope),
                "addresses": _clickhouse_array_literal(wanted),
            },
        )
        return frozenset(str(row["thread_id"]) for row in rows)


def _clickhouse_datetime(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
