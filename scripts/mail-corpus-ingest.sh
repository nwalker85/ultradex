#!/usr/bin/env bash
# Run the private mail-corpus ingest with 1Password-resolved credentials.
# Secrets reach the process environment via `op run` and never touch disk or argv.
#
#   MAIL_CLICKHOUSE_USER=mail_ingest scripts/mail-corpus-ingest.sh --dry-run --max-messages 20
#
# MAIL_CLICKHOUSE_USER is intentionally NOT in the template: the `default` user on
# vakr reaches every database on the host, so naming the user is an operator
# decision that has to be made out loud, every run, until a scoped user exists.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TEMPLATE="${MAIL_CORPUS_ENV_TEMPLATE:-$REPO_ROOT/scripts/mail-corpus.env.tpl}"
PYTHON="${PYTHON:-python3}"

need() { command -v "$1" >/dev/null 2>&1 || { printf 'missing %s\n' "$1" >&2; exit 1; }; }
need op

if ! op whoami >/dev/null 2>&1; then
  printf 'op is not signed in. Run: eval $(op signin)\n' >&2
  exit 1
fi

if [ -z "${MAIL_CLICKHOUSE_USER:-}" ]; then
  printf 'MAIL_CLICKHOUSE_USER is unset — there is no default.\n' >&2
  printf 'The ClickHouse `default` user reaches every database on vakr, including forensics.\n' >&2
  printf 'Export the user you intend to write as, e.g. MAIL_CLICKHOUSE_USER=mail_ingest\n' >&2
  exit 2
fi

[ -f "$ENV_TEMPLATE" ] || { printf 'missing env template: %s\n' "$ENV_TEMPLATE" >&2; exit 1; }

cd "$REPO_ROOT"
exec op run --env-file="$ENV_TEMPLATE" -- \
  "$PYTHON" -m cli.ingest_mail_corpus "$@"
