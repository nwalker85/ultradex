# Mail corpus ingest — Gmail → ClickHouse (private Stage)

Implements `~/docs/30-projects/career-command-center/DESIGN-mail-corpus-clickhouse.md`.

This is the **private Stage** under AAL Sense. It is not the governed plane.
The governed `jobsearch_evidence_refs` keeps its commitment plus a 240-char
redacted summary and never holds bodies — that is the Vór rule and nothing here
changes it. Promotion from Stage to governed evidence goes through Consent.

## What is where

| Path | What it is |
|---|---|
| `core/mail_corpus.py` | The chunker. Nine-part taxonomy, template collapse. Pure functions. |
| `core/mail_clickhouse.py` | DDL for `mail.messages` / `mail.chunks` / `mail.embeddings`, plus the idempotent writer. HTTP via `httpx`. |
| `core/mail_gmail.py` | Full-message fetch and MIME → plaintext. Reuses `core.jobsearch_gmail` auth. |
| `core/mail_ingest.py` | Newest-first backfill orchestration. |
| `cli/ingest_mail_corpus.py` | Entry point. |
| `scripts/mail-corpus-ingest.sh` | `op run` wrapper — secrets never touch disk or argv. |

The governed sweep in `core/jobsearch_gmail.py` and `cli/sense_gmail.py` is
untouched: it still stores thread IDs, a commitment and counts only.

## Credentials

Gmail reuses the governed sense OAuth app
(`op://ravenmask/Gmail OAuth - CCC Sense`): `GMAIL_ACCESS_TOKEN`, or
`GMAIL_CLIENT_ID` + `GMAIL_CLIENT_SECRET` + `GMAIL_REFRESH_TOKEN`.

ClickHouse has **no credential default**:

| Variable | Default | Notes |
|---|---|---|
| `MAIL_CLICKHOUSE_URL` | `http://vakr.ravenmask.net:8123` | HTTP interface |
| `MAIL_CLICKHOUSE_USER` | *(none — required)* | see below |
| `MAIL_CLICKHOUSE_PASSWORD` | *(none — required)* | empty needs `MAIL_CLICKHOUSE_ALLOW_EMPTY_PASSWORD=1` |
| `MAIL_CLICKHOUSE_DATABASE` | `mail` | |
| `MAIL_CLICKHOUSE_TIMEOUT` | `60` | seconds |

The user is required and undefaulted **on purpose**. The `default` user on vakr
reaches every database on the host, including `forensics`. Open item 1 in the
design ("a dedicated `mail` user with grants scoped to that database is the
minimum") is not closed, so the code refuses to guess. Credentials travel as
`X-ClickHouse-User` / `X-ClickHouse-Key` headers, never in the URL.

## Running it

```bash
# schema only — prints, touches nothing
python -m cli.ingest_mail_corpus --print-ddl

# apply DDL (idempotent)
MAIL_CLICKHOUSE_USER=… scripts/mail-corpus-ingest.sh --schema-only

# look before you leap: real mail, real segmentation, nothing written
scripts/mail-corpus-ingest.sh --dry-run --max-messages 20

# small verified sample
MAIL_CLICKHOUSE_USER=… scripts/mail-corpus-ingest.sh --init-schema --max-messages 50

# the backfill — newest-first, resumable, safe to re-run
MAIL_CLICKHOUSE_USER=… scripts/mail-corpus-ingest.sh
MAIL_CLICKHOUSE_USER=… scripts/mail-corpus-ingest.sh --resume
MAIL_CLICKHOUSE_USER=… scripts/mail-corpus-ingest.sh --counts
```

## Idempotency

Three layers, because re-running ingest is something you will do:

1. **ReplacingMergeTree** collapses exact duplicates at merge time. The sort
   key is the dedup key — `(thread_id, ts, message_id)` for messages,
   `(message_id, seq)` for chunks.
2. **Skip-before-fetch.** Each page's IDs are checked against
   `mail.messages` first, so a re-run costs one `SELECT` per page instead of a
   full re-fetch. `--force` opts out.
3. **Deterministic rows.** Segmentation is a pure function of the message, so
   the same message always produces the same rows. Only `ingested_at`
   (the ReplacingMergeTree version) moves.

Caveat worth knowing: if the chunker later produces *fewer* chunks for a
message, the surplus high-`seq` rows from the earlier run stay until TTL —
ReplacingMergeTree collapses duplicate keys, it does not delete orphans. A
chunker change that shortens output wants
`ALTER TABLE mail.chunks DELETE WHERE message_id IN (…)` before the re-ingest.

## Backfill order

Newest-first. Gmail returns `users.messages.list` in reverse-chronological
order, and each page is written before the next is requested, so the corpus is
queryable within a minute rather than after the full three-year pull. `--resume`
reads `min(ts)` out of `mail.messages` and appends `before:YYYY/MM/DD` to the
query; the day-granularity overlap is absorbed by layers 1 and 2 above.

## The chunker

Nine parts, all **stored**, only two **embedded**:

| `part` | Embed? |
|---|---|
| `subject` | yes |
| `body` | yes |
| `quoted`, `signature`, `greeting`, `disclaimer`, `boilerplate`, `forward_header`, `autoreply` | no |

Boundary detection is heuristic and will be wrong at the edges. That is
acceptable by design: **Consent is the labeler**. Every promote and discard is
a training example against a chunk that already carries a `part`.

`template_id` is a hash of the chunk with variable spans normalised — names,
dates, times, counts, money, URLs, addresses, phone numbers. Two hundred
LinkedIn digests with a name swapped share one `template_id`. Instances keep
their own rows; `core.mail_corpus.embeddable_exemplars` picks one exemplar per
`(part, template_id)` for the embedding stage.

`--max-body-chars` (default 2000) splits long body spans on paragraph
boundaries. A chunk is an embedding unit; a 40 KB newsletter body is not one.

## Not built here

- `mail.embeddings` is **created** but nothing writes to it. Which model, and
  whether it runs on Fenrir, is design open item 2.
- No scoped ClickHouse user or grants — design open item 1, operator decision.
- No at-rest encryption.
