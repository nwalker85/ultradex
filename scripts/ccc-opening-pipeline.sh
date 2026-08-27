#!/usr/bin/env bash
# Create organization -> job opening (lead) -> application via governed commands.
# Requires ULTRADEX_API_TOKEN and a running Ultradex API (default http://127.0.0.1:8001).
set -euo pipefail

BASE_URL="${ULTRADEX_BASE_URL:-http://127.0.0.1:8001}"
TOKEN="${ULTRADEX_API_TOKEN:?Set ULTRADEX_API_TOKEN}"
TS="$(date +%s)"

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <org_name> <org_domain> <job_title> [linkedin_url]" >&2
  exit 1
fi

ORG_NAME="$1"
ORG_DOMAIN="$2"
JOB_TITLE="$3"
JOB_URL="${4:-}"

auth=( -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" )

submit() {
  local cmd="$1" key="$2" body="$3"
  curl -fsS -X POST "${BASE_URL}/api/v2/job-search/commands/${cmd}" \
    "${auth[@]}" -H "Idempotency-Key: ${key}" -d "${body}"
}

wait_row() {
  local sql="$1" tries="${2:-20}"
  local val=""
  for _ in $(seq 1 "$tries"); do
    val="$(psql "${DATABASE_URL}" -tAc "$sql" 2>/dev/null || true)"
    val="${val// /}"
    if [[ -n "$val" ]]; then echo "$val"; return 0; fi
    sleep 1
  done
  return 1
}

echo "Creating organization: ${ORG_NAME}" >&2
submit organizations.create "ccc-${TS}-org" \
  "$(python3 - <<PY
import json,sys
print(json.dumps({"name": sys.argv[1], "domain": sys.argv[2]}))
PY
"$ORG_NAME" "$ORG_DOMAIN")" >/dev/null

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Set DATABASE_URL to poll for created IDs, or read operation status URLs from API responses." >&2
  exit 0
fi

ORG_ID="$(wait_row "SELECT id FROM jobsearch_organizations WHERE name='${ORG_NAME//\'/''}' ORDER BY created_at DESC LIMIT 1")"
echo "organization_id=${ORG_ID}" >&2

LEAD_BODY="$(python3 - <<PY
import json,sys
payload = {
  "employer": sys.argv[1],
  "organization_id": sys.argv[2],
  "title": sys.argv[3],
  "source_board": "manual",
  "location": "unspecified",
}
if sys.argv[4]:
  payload["url"] = sys.argv[4]
print(json.dumps(payload))
PY
"$ORG_NAME" "$ORG_ID" "$JOB_TITLE" "$JOB_URL")"

echo "Creating lead (opening): ${JOB_TITLE}" >&2
submit leads.create "ccc-${TS}-lead" "$LEAD_BODY" >/dev/null
LEAD_ID="$(wait_row "SELECT id FROM jobsearch_leads WHERE organization_id='${ORG_ID}' ORDER BY created_at DESC LIMIT 1")"
echo "lead_id=${LEAD_ID}" >&2

echo "Converting lead to opportunity + application" >&2
submit leads.convert "ccc-${TS}-convert" \
  "$(python3 - <<PY
import json,sys
print(json.dumps({
  "lead_id": sys.argv[1],
  "stage": "applied",
  "occurred_at": "2026-08-27T06:00:00Z",
  "custom_title": f"{sys.argv[2]} — {sys.argv[3]}",
}))
PY
"$LEAD_ID" "$ORG_NAME" "$JOB_TITLE")" >/dev/null

APP_ID="$(wait_row "SELECT id FROM jobsearch_applications ORDER BY created_at DESC LIMIT 1")"
OPP_ID="$(wait_row "SELECT converted_opportunity_id FROM jobsearch_leads WHERE id='${LEAD_ID}'")"

echo "organization_id=${ORG_ID}"
echo "lead_id=${LEAD_ID}"
echo "opportunity_id=${OPP_ID}"
echo "application_id=${APP_ID}"
