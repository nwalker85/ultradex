# 1Password template for the private mail-corpus ingest. `op run` resolves these
# into the child process environment — nothing is ever written to disk.
# Values live in 1Password; only op:// references belong in this file.
#
#   op run --env-file=scripts/mail-corpus.env.tpl -- python -m cli.ingest_mail_corpus --dry-run

# Gmail — same OAuth app as the governed sense sweep.
GMAIL_CLIENT_ID=op://ravenmask/Gmail OAuth - CCC Sense/client_id
GMAIL_CLIENT_SECRET=op://ravenmask/Gmail OAuth - CCC Sense/client_secret
GMAIL_REFRESH_TOKEN=op://ravenmask/Gmail OAuth - CCC Sense/refresh_token

# ClickHouse endpoint. Credentials are deliberately absent from this template:
# MAIL_CLICKHOUSE_USER must be exported by the operator, because the `default`
# user on vakr reaches every database on the host (including `forensics`).
# Once a scoped user exists, add its own op:// reference here.
MAIL_CLICKHOUSE_URL=http://vakr.ravenmask.net:8123
MAIL_CLICKHOUSE_DATABASE=mail
MAIL_CLICKHOUSE_PASSWORD=op://ravenmask/Heimdall ClickStack - Vakr/CLICKHOUSE_PASSWORD
