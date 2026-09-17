#!/usr/bin/env bash
# LinkedIn owed-replies, one pass: scan the signed-in inbox through the mcp-chrome bridge in
# Nate's Chrome and post owed replies to Odin's Runes.
#   scripts/linkedin-owed-replies-run.sh            dry run (prints the plan)
#   scripts/linkedin-owed-replies-run.sh --post     create/close tasks
#
# Laptop-bound: the bridge (hangwin/mcp-chrome, 127.0.0.1:12306) exists only where Nate's
# Chrome is running with the extension connected. Same scheduling shape as
# owed-replies-run.sh: n8n owns the cadence and kicks a launchd job over SSH; this script is
# the body. Runs from the checkout it lives in; contacts come from the cached CCC snapshot the
# mail pass maintains. The Chrome window never gains focus (DOM-only, background:true).
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-$WT/.venv311/bin/python}"
CONTACTS="${CCC_CONTACTS_FILE:-$HOME/var/ccc/contacts.json}"
HUB="${ODINSRUNES_API_URL:-http://100.106.47.41:8765}"
BRIDGE="${MCP_CHROME_URL:-http://127.0.0.1:12306/mcp}"
cd "$WT"
if ! lsof -nP -iTCP:12306 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "== $(date -u +%FT%TZ) SKIPPED: mcp-chrome bridge not listening on 12306 (Chrome/extension not connected)"
  exit 0
fi
LOCK="$WT/.linkedin-owed-replies.lock"
exec 9>>"$LOCK"
LOCK_STATE=$("$PY" -c '
import fcntl
try:
    fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB); print("acquired")
except BlockingIOError:
    print("held")
')
if [ "$LOCK_STATE" != "acquired" ]; then
  echo "== $(date -u +%FT%TZ) SKIPPED: previous pass still running (lock held: $LOCK)"
  exit 0
fi
echo "== $(date -u +%FT%TZ) checkout $WT @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
ARGS=--dry-run; [ "${1:-}" = "--post" ] && ARGS=
CCC_CONTACTS_FILE="$CONTACTS" ODINSRUNES_API_URL="$HUB" MCP_CHROME_URL="$BRIDGE" "$PY" -m cli.linkedin_owed_replies $ARGS
