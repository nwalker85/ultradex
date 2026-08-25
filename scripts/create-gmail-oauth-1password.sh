#!/usr/bin/env bash
# Mint a Gmail readonly refresh token and store it in 1Password.
#
#   scripts/create-gmail-oauth-1password.sh \
#     --client-secret ./client_secret.json \
#     --username you@gmail.com
#
# Prerequisites: `op` signed in, python3, a Desktop OAuth client JSON from GCP.
# Secrets go in through a 1Password JSON template, not argv.

set -euo pipefail
umask 077

readonly VAULT_DEFAULT="ravenmask"
readonly TITLE_DEFAULT="Gmail OAuth - CCC Sense"
readonly SCOPE="https://www.googleapis.com/auth/gmail.readonly"
readonly HOSTNAME="gmail.googleapis.com"
readonly TAGS="gmail,oauth,ccc,ultradex"
readonly REDIRECT_PORT_DEFAULT="8765"

usage() {
  cat <<'EOF'
Create 1Password item "Gmail OAuth - CCC Sense" for UltraDex Gmail Sense.

Usage:
  scripts/create-gmail-oauth-1password.sh --client-secret FILE --username EMAIL
  scripts/create-gmail-oauth-1password.sh --client-secret FILE --username EMAIL --replace
  scripts/create-gmail-oauth-1password.sh --print-gcp-steps

Options:
  --client-secret FILE   Desktop (or Web) OAuth client JSON from GCP
  --username EMAIL       Google account Sense will read
  --vault NAME           1Password vault (default: ravenmask)
  --title TITLE          Item title (default: Gmail OAuth - CCC Sense)
  --replace              Recreate the item if it already exists
  --redirect-port PORT   Loopback port (default: 8765). Must match GCP.
  --print-gcp-steps      Print the Google Cloud setup and exit
  -h, --help             Show this help

The script opens a local browser for Google consent (gmail.readonly only),
writes the 1Password item, then deletes the local token material.

Redirect URI this script uses (register both on a Web client):
  http://127.0.0.1:8765/
  http://localhost:8765/
Desktop clients allow loopback without registration. Prefer Desktop.
EOF
}

print_gcp_steps() {
  cat <<'EOF'
Google Cloud — one-time setup

1. Open the GCP project you already use for Google APIs.
2. Enable the Gmail API.
3. Google Auth Platform → Audience:
   User type stays External (personal Gmail cannot pick Internal).
   Publishing status stays Testing. Do not publish. Do not start verification.
   Test users → Add users → the SAME personal Gmail you will sign in with.
   That is allowed. Test users are not Workspace-only.
   Consent will still say the app is unverified. Use Advanced → continue.
4. Credentials → Create OAuth client ID → Desktop app (preferred)
   Name it: ccc-gmail-sense
   Desktop clients do not need a redirect URI.
5. If you already created a Web client, edit it and add BOTH:
     http://127.0.0.1:8765/
     http://localhost:8765/
   Trailing slash required. Save, wait a few seconds, then re-run.
6. Download the JSON. Pass that file as --client-secret.
   Do not commit it.

Then run:

  scripts/create-gmail-oauth-1password.sh \
    --client-secret ~/Downloads/client_secret.json \
    --username YOUR_GOOGLE_ACCOUNT
EOF
}

fail() {
  printf 'gmail-oauth-1password: %s\n' "$1" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

CLIENT_SECRET=""
USERNAME=""
VAULT="$VAULT_DEFAULT"
TITLE="$TITLE_DEFAULT"
REPLACE=0
REDIRECT_PORT="$REDIRECT_PORT_DEFAULT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client-secret)
      [[ $# -ge 2 ]] || fail "--client-secret needs a file path"
      CLIENT_SECRET="$2"
      shift 2
      ;;
    --username)
      [[ $# -ge 2 ]] || fail "--username needs an email"
      USERNAME="$2"
      shift 2
      ;;
    --vault)
      [[ $# -ge 2 ]] || fail "--vault needs a name"
      VAULT="$2"
      shift 2
      ;;
    --title)
      [[ $# -ge 2 ]] || fail "--title needs a value"
      TITLE="$2"
      shift 2
      ;;
    --replace)
      REPLACE=1
      shift
      ;;
    --redirect-port)
      [[ $# -ge 2 ]] || fail "--redirect-port needs a port"
      REDIRECT_PORT="$2"
      shift 2
      ;;
    --print-gcp-steps)
      print_gcp_steps
      exit 0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

if [[ -z "$CLIENT_SECRET" || -z "$USERNAME" ]]; then
  usage
  printf '\n' >&2
  print_gcp_steps
  exit 2
fi

[[ -f "$CLIENT_SECRET" ]] || fail "client secret file not found: $CLIENT_SECRET"
[[ "$USERNAME" == *"@"* ]] || fail "username must be an email address"

need_cmd op
need_cmd python3

if ! op whoami >/dev/null 2>&1; then
  fail "op is not signed in. Run: eval \$(op signin)"
fi

if op item get "$TITLE" --vault "$VAULT" >/dev/null 2>&1; then
  if [[ "$REPLACE" -ne 1 ]]; then
    fail "item already exists: $TITLE (pass --replace to recreate it)"
  fi
fi

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/ccc-gmail-oauth.XXXXXX")"
cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

python3 - "$CLIENT_SECRET" "$REDIRECT_PORT" "$WORKDIR/client.json" "$WORKDIR/client_type" <<'PY'
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
port = sys.argv[2]
dest = Path(sys.argv[3])
type_file = Path(sys.argv[4])
raw = json.loads(src.read_text())
if "installed" in raw:
    kind = "installed"
    block = raw["installed"]
elif "web" in raw:
    kind = "web"
    block = raw["web"]
else:
    raise SystemExit("client secret JSON must have an 'installed' or 'web' object")
if not isinstance(block, dict):
    raise SystemExit("client secret block must be an object")
client_id = block.get("client_id") or ""
client_secret = block.get("client_secret") or ""
if not client_id or not client_secret:
    raise SystemExit("client secret JSON is missing client_id or client_secret")
redirects = [
    f"http://127.0.0.1:{port}/",
    f"http://localhost:{port}/",
]
payload = {
    kind: {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": block.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": block.get("token_uri", "https://oauth2.googleapis.com/token"),
        "redirect_uris": redirects,
    }
}
dest.write_text(json.dumps(payload, indent=2))
type_file.write_text(kind)
print(f"client_type={kind}")
print(f"client_id_len={len(client_id)}")
print(f"client_secret_len={len(client_secret)}")
print(f"redirect_uri=http://127.0.0.1:{port}/")
print(f"redirect_uri=http://localhost:{port}/")
PY

CLIENT_TYPE="$(cat "$WORKDIR/client_type")"
printf '\nRegister these Authorized redirect URIs on a Web OAuth client:\n'
printf '  http://127.0.0.1:%s/\n' "$REDIRECT_PORT"
printf '  http://localhost:%s/\n' "$REDIRECT_PORT"
if [[ "$CLIENT_TYPE" == "web" ]]; then
  printf '\nThis JSON is a Web client. Save those URIs in GCP, then press Enter.\n'
  read -r
else
  printf 'Desktop client detected — loopback should work without registration.\n'
fi

python3 -m venv "$WORKDIR/venv"
# shellcheck disable=SC1091
source "$WORKDIR/venv/bin/activate"
pip install --quiet --disable-pip-version-check 'google-auth-oauthlib>=1.2'

python3 - "$WORKDIR/client.json" "$SCOPE" "$REDIRECT_PORT" "$WORKDIR/refresh.token" <<'PY'
from pathlib import Path
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

client_file, scope, port, out_file = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
flow = InstalledAppFlow.from_client_secrets_file(client_file, scopes=[scope])
creds = flow.run_local_server(
    host="127.0.0.1",
    port=port,
    prompt="consent",
    open_browser=True,
)
if not creds.refresh_token:
    raise SystemExit("Google did not return a refresh_token. Re-run with prompt=consent and revoke the app if you consented before.")
Path(out_file).write_text(creds.refresh_token)
print(f"refresh_token_len={len(creds.refresh_token)}")
PY

python3 - "$WORKDIR/client.json" "$WORKDIR/refresh.token" "$USERNAME" "$TITLE" "$VAULT" "$SCOPE" "$HOSTNAME" "$TAGS" "$WORKDIR/item.json" <<'PY'
import json
import sys
from pathlib import Path

raw_client = json.loads(Path(sys.argv[1]).read_text())
client = raw_client.get("installed") or raw_client.get("web")
if not client:
    raise SystemExit("normalized client JSON missing installed/web")
refresh = Path(sys.argv[2]).read_text().strip()
username, title, vault, scope, hostname, tags = sys.argv[3:9]
dest = Path(sys.argv[9])
dest.write_text(json.dumps({
    "title": title,
    "category": "LOGIN",
    "vault": {"name": vault},
    "tags": [tag for tag in tags.split(",") if tag],
    "fields": [
        {
            "id": "username",
            "type": "STRING",
            "purpose": "USERNAME",
            "label": "username",
            "value": username,
        },
        {
            "id": "notesPlain",
            "type": "STRING",
            "purpose": "NOTES",
            "label": "notesPlain",
            "value": (
                "CCC Gmail Sense (UltraDex). Readonly. "
                "Do not add send/modify scopes. "
                f"op://{vault}/{title}/refresh_token"
            ),
        },
        {"id": "client_id", "type": "CONCEALED", "label": "client_id", "value": client["client_id"]},
        {"id": "client_secret", "type": "CONCEALED", "label": "client_secret", "value": client["client_secret"]},
        {"id": "refresh_token", "type": "CONCEALED", "label": "refresh_token", "value": refresh},
        {"id": "scopes", "type": "STRING", "label": "scopes", "value": scope},
        {"id": "hostname", "type": "STRING", "label": "hostname", "value": hostname},
    ],
}))
print("template_written=yes")
PY

if [[ "$REPLACE" -eq 1 ]] && op item get "$TITLE" --vault "$VAULT" >/dev/null 2>&1; then
  op item delete "$TITLE" --vault "$VAULT" >/dev/null
fi

ITEM_JSON="$(op item create --vault "$VAULT" --template "$WORKDIR/item.json" --format=json)"
python3 -c 'import json,sys
item=json.loads(sys.argv[1])
print("item="+item.get("title",""))
print("vault="+((item.get("vault") or {}).get("name") or ""))
print("id="+item.get("id",""))
fields={ (f.get("label") or f.get("id")): bool(f.get("value")) for f in item.get("fields") or [] }
for name in ("username","client_id","client_secret","refresh_token","scopes","hostname"):
    print(f"has_{name}="+str(fields.get(name, False)).lower())
' "$ITEM_JSON"

printf '\nReference: op://%s/%s/refresh_token\n' "$VAULT" "$TITLE"
printf 'Local OAuth files were deleted on exit.\n'
