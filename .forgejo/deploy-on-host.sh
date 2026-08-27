#!/usr/bin/env bash
set -euo pipefail
# Profile A host-side deploy — CCC on k0s/vakr (ccc-tmp).
# Builds local ccc/*:dev images, imports via k0s ctr, rollout restart.
#
# Env: SHA REPO  [FORCE_SERVICES] [DRY_RUN=1]
: "${SHA:?}"; : "${REPO:?}"
DRY_RUN="${DRY_RUN:-0}"; FORCE_SERVICES="${FORCE_SERVICES:-}"

# shellcheck source=/dev/null
source "$(dirname "$0")/scope-lib.sh"

declare -A IMG CTX PREFIX FILE
declare -A SECRET SECRETSRC
load_service_map

declare -A want
BASELINE=""
git rev-parse -q --verify HEAD~1 >/dev/null 2>&1 && BASELINE="HEAD~1"
compute_scope want "$BASELINE"

set +u; nwant=${#want[@]}; set -u
if [ "$nwant" -eq 0 ]; then
  echo "No deploy-affecting changes — skipping."
  exit 0
fi
echo "scoped services: ${!want[*]}"
[ "$DRY_RUN" = "1" ] && { echo "(dry-run) stopping before deploy."; exit 0; }

need_api=0
need_glass=0
for svc in "${!want[@]}"; do
  case "$svc" in
    api|api_* ) need_api=1 ;;
    glass|glass_* ) need_glass=1 ;;
    * ) echo "unknown scoped service: $svc" >&2; exit 1 ;;
  esac
done

deploy_list=()
[ "$need_api" = 1 ] && deploy_list+=(api)
[ "$need_glass" = 1 ] && deploy_list+=(glass)
DEPLOY_SERVICES=$(IFS=,; echo "${deploy_list[*]}")

echo "==> deploy-k0s services=${DEPLOY_SERVICES} sha=${SHA:0:12}"
SHA="$SHA" DEPLOY_SERVICES="$DEPLOY_SERVICES" bash scripts/deploy-k0s.sh
echo "DEPLOY_LIST=${DEPLOY_SERVICES}"
