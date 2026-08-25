#!/usr/bin/env bash
# Load Gmail Sense OAuth fields from 1Password into the dedicated k0s secret.
# Values never go on argv. Prints key names only.

set -euo pipefail
umask 077

readonly ITEM="Gmail OAuth - CCC Sense"
readonly VAULT="ravenmask"
readonly NAMESPACE="${CCC_NAMESPACE:-ccc-tmp}"
readonly SECRET_NAME="gmail-sense"

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/vakr-k0s.yaml}"

need() { command -v "$1" >/dev/null 2>&1 || { printf 'missing %s\n' "$1" >&2; exit 1; }; }
need op

if ! op whoami >/dev/null 2>&1; then
  printf 'op is not signed in. Run: eval $(op signin)\n' >&2
  exit 1
fi

apply_secret() {
  if command -v kubectl >/dev/null 2>&1 \
    && kubectl --request-timeout=4s -n "$NAMESPACE" get ns "$NAMESPACE" >/dev/null 2>&1; then
    kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
      --from-env-file="$1" \
      --dry-run=client -o yaml | kubectl apply -f -
    kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o json
    return
  fi
  need ssh
  ssh -o ConnectTimeout=10 vakr-svc \
    'umask 077; cat > /tmp/ccc-gmail-sense.env; sudo k0s kubectl -n '"$NAMESPACE"' create secret generic '"$SECRET_NAME"' --from-env-file=/tmp/ccc-gmail-sense.env --dry-run=client -o yaml | sudo k0s kubectl apply -f -; rm -f /tmp/ccc-gmail-sense.env; sudo k0s kubectl -n '"$NAMESPACE"' get secret '"$SECRET_NAME"' -o json' \
    < "$1"
}

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/ccc-gmail-sense.XXXXXX")"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

cat > "$WORKDIR/template.env" <<'EOF'
GMAIL_CLIENT_ID={{ op://ravenmask/Gmail OAuth - CCC Sense/client_id }}
GMAIL_CLIENT_SECRET={{ op://ravenmask/Gmail OAuth - CCC Sense/client_secret }}
GMAIL_REFRESH_TOKEN={{ op://ravenmask/Gmail OAuth - CCC Sense/refresh_token }}
EOF
op inject -i "$WORKDIR/template.env" -o "$WORKDIR/env"

python3 - "$WORKDIR/env" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
required = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")
present = []
for line in path.read_text().splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if value.strip():
        present.append(key)
missing = [key for key in required if key not in present]
if missing:
    raise SystemExit("gmail-sense-secret: missing fields: " + ",".join(missing))
print("fields=" + ",".join(required))
PY

apply_secret "$WORKDIR/env" | python3 -c '
import json,sys
text=sys.stdin.read()
item=json.loads(text[text.find("{"):])
keys=sorted((item.get("data") or {}).keys())
print("secret="+item.get("metadata",{}).get("name",""))
print("keys="+",".join(keys))
'
