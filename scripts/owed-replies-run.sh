#!/usr/bin/env bash
# CCC mail pipeline, one pass: ingest both mailboxes (30d window, idempotent) into ClickHouse,
# refresh the CCC contact list from vakr, rank owed replies, post them to Odin's Runes.
#   scripts/owed-replies-run.sh            dry run (prints the plan)
#   scripts/owed-replies-run.sh --post     create/update tasks
#
# Runs from the checkout it lives in (a `main` worktree with its own .venv311), never from
# ~/tmp pointing into a feature worktree (custody: a disposable worktree is not a home for a
# scheduled job — supervisor ruling 2026-09-15). Triggered by n8n (workflow Rj3FpJxk9l9lsMMs,
# every 15 min) over an SSH forced command that kickstarts launchd `dev.ravenhelm.ccc-owed-replies`;
# launchd is transport only (no StartInterval), n8n owns the cadence. Secrets resolve inside `op run`.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-$WT/.venv311/bin/python}"
[ -x "$PY" ] || PY="/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/main-live/.venv311/bin/python"
A="${MAIL_CORPUS_ENV_A:-$HOME/tmp/mail-corpus-admin.env.tpl}"            # gmail (nwalker85) + shared endpoints
B="${MAIL_CORPUS_ENV_B:-$HOME/tmp/mail-corpus-ravenhelm-co.env.tpl}"     # nate@ravenhelm.co
CONTACTS="${CCC_CONTACTS_FILE:-$HOME/var/ccc/contacts.json}"
HUB="${ODINSRUNES_API_URL:-http://100.106.47.41:8765}"
PERIOD_SECONDS="${OWED_REPLIES_PERIOD_SECONDS:-900}"   # the n8n cadence; a run near it is reported
mkdir -p "$(dirname "$CONTACTS")"
cd "$WT"
START=$(date +%s)
# Overlap guard. A pass takes ~10 min on a 15-min timer; a slow Gmail page or a hung request
# would let tick N+1 start while tick N is still writing to the hub, and two interleaved update
# paths can retitle from stale state or clobber an edit Nate made in between — silently, both
# exiting 0. macOS ships no flock(1), so the lock is fcntl.flock on fd 9 from this checkout's
# Python; the shell keeps fd 9 open, so the lock lives exactly as long as this pass. Non-blocking:
# a held lock means the tick is SKIPPED, logged, exit 0 — visible, not silent.
LOCK="$WT/.owed-replies.lock"
exec 9>>"$LOCK"    # opening takes no lock; only flock() below does
LOCK_STATE=$("$PY" -c '
import fcntl
try:
    fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)   # acquired: held by fd 9 until this shell exits
    print("acquired")
except BlockingIOError:
    print("held")                                    # another pass owns it
')
if [ "$LOCK_STATE" != "acquired" ]; then
  echo "== $(date -u +%FT%TZ) SKIPPED: previous pass still running (lock held: $LOCK)"
  exit 0
fi
echo "== $(date -u +%FT%TZ) checkout $WT @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
echo "== ingest gmail"
MAIL_CORPUS_ENV_TEMPLATE="$A" MAIL_CLICKHOUSE_USER=default PYTHON="$PY" \
  scripts/mail-corpus-ingest.sh --extra-query "newer_than:30d" --max-messages 3000 2>&1 | tail -2 || echo "== WARNING: gmail ingest returned non-zero (check OAuth tokens); continuing"
echo "== ingest ravenhelm.co"
MAIL_CORPUS_ENV_TEMPLATE="$B" MAIL_CLICKHOUSE_USER=default PYTHON="$PY" \
  scripts/mail-corpus-ingest.sh --extra-query "newer_than:30d" --max-messages 3000 2>&1 | tail -2 || echo "== WARNING: ravenhelm.co ingest returned non-zero; continuing"
echo "== contacts from vakr"
TMP=$(mktemp "$(dirname "$CONTACTS")/contacts.XXXXXX")
TIMEOUT_BIN=$(command -v timeout || echo "")
if [ -n "$TIMEOUT_BIN" ]; then SSH_RUN="$TIMEOUT_BIN 6s ssh"; else SSH_RUN="ssh"; fi
if $SSH_RUN -o BatchMode=yes -o ConnectTimeout=5 vakr-ts-svc 'T=$(sudo k0s kubectl -n ccc-tmp get secret ultradex -o jsonpath="{.data.ULTRADEX_API_TOKEN}" | base64 -d); curl -fsS -m 30 -H "Authorization: Bearer $T" http://10.10.20.101:30800/api/v1/contacts' 2>/dev/null | grep -v '^#' > "$TMP" && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$TMP"; then
  mv "$TMP" "$CONTACTS"; echo "contacts refreshed: $(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$CONTACTS")"
else
  rm -f "$TMP"; echo "contacts refresh failed; using cached $CONTACTS"
fi
echo "== email owed replies"
ARGS=--dry-run; [ "${1:-}" = "--post" ] && ARGS=
op run --env-file="$A" -- env CCC_CONTACTS_FILE="$CONTACTS" ODINSRUNES_API_URL="$HUB" "$PY" -m cli.owed_replies $ARGS
echo "== linkedin owed replies"
if lsof -nP -iTCP:12306 -sTCP:LISTEN >/dev/null 2>&1; then
  PYTHON="$PY" scripts/linkedin-owed-replies-run.sh "${1:-}" || echo "== WARNING: linkedin scan failed"
else
  echo "== SKIPPED: mcp-chrome bridge not listening on 12306"
fi
echo "== hub ccc_email tasks"
curl -s -m 8 "$HUB/api/tasks?source=ccc_email&limit=50" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("count", d["count"]); [print(" ", i["status"], "|", i["title"][:90]) for i in d["items"]]'
echo "== hub ccc_linkedin tasks"
curl -s -m 8 "$HUB/api/tasks?source=ccc_linkedin&limit=50" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("count", d.get("count", len(d.get("items", [])))); [print(" ", i.get("status"), "|", i.get("title","")[:90]) for i in d.get("items",[])]'
ELAPSED=$(( $(date +%s) - START ))
NOTE=""; [ "$ELAPSED" -ge $(( PERIOD_SECONDS * 8 / 10 )) ] && NOTE=" WARNING: runtime is ${ELAPSED}s against a ${PERIOD_SECONDS}s period — the next tick will be skipped by the lock"
echo "DONE $(date -u +%FT%TZ) elapsed=${ELAPSED}s${NOTE}"
