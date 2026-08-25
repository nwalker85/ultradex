# 1Password template for the private mail-corpus ingest. `op run` resolves these
# into the child process environment — nothing is ever written to disk.
# Values live in 1Password; only op:// references belong in this file.
#
#   op run --env-file=scripts/mail-corpus.env.tpl -- python -m cli.ingest_mail_corpus --dry-run

# Gmail — same OAuth app as the governed sense sweep.
GMAIL_CLIENT_ID=op://ravenmask/Gmail OAuth - CCC Sense/client_id
GMAIL_CLIENT_SECRET=op://ravenmask/Gmail OAuth - CCC Sense/client_secret
GMAIL_REFRESH_TOKEN=op://ravenmask/Gmail OAuth - CCC Sense/refresh_token

# ClickHouse. `gmailnwalker85` is scoped to exactly this one mail account and
# this one database — it cannot read `forensics` or `heimdall`. One database
# and one user per account; other addresses and providers get their own.
MAIL_CLICKHOUSE_URL=http://vakr.ravenmask.net:8123
MAIL_CLICKHOUSE_DATABASE=gmailnwalker85
MAIL_CLICKHOUSE_USER=gmailnwalker85
MAIL_CLICKHOUSE_PASSWORD=op://ravenmask/ClickHouse gmailnwalker85 - Vakr/password

# Embeddings: odin llama-swap, OpenAI-compatible /v1/embeddings. Internal DNS,
# not the tailnet IP. Same model and window discipline as audio-app.
EMBED_API_URL=http://odin.ravenmask.net:18090
EMBED_MODEL=nomic-embed-text
