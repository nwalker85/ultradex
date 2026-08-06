#!/usr/bin/env bash
set -euo pipefail
# Profile B host-side step (runs as ravenmask@hrafngud, cwd = repo clone @ $SHA).
# Builds + pushes to Harbor the images whose paths changed in the merge (HEAD~1..HEAD)
# or the explicit FORCE_SERVICES list. NO deploy — the image is consumed/deployed
# elsewhere (e.g. Argo/Helm on Norns, or another repo's compose). Fail-fast.
#
# Env: SHA REGISTRY HARBOR_PROJECT REPO HU HP  [FORCE_SERVICES] [DRY_RUN=1]
: "${SHA:?}"; : "${REGISTRY:?}"; : "${HARBOR_PROJECT:?}"; : "${REPO:?}"
DRY_RUN="${DRY_RUN:-0}"; FORCE_SERVICES="${FORCE_SERVICES:-}"

# shellcheck source=/dev/null
source "$(dirname "$0")/scope-lib.sh"

declare -A IMG CTX PREFIX FILE
declare -A SECRET SECRETSRC
load_service_map

# B is stateless: scope against the merge delta (HEAD~1..HEAD). Missing parent => FULL.
declare -A want
BASELINE=""
git rev-parse -q --verify HEAD~1 >/dev/null 2>&1 && BASELINE="HEAD~1"
compute_scope want "$BASELINE"

set +u; nwant=${#want[@]}; set -u
if [ "$nwant" -eq 0 ]; then
  echo "No image-affecting changes — skipping build/push."
  exit 0
fi
echo "images to build+push: ${!want[*]}"
[ "$DRY_RUN" = "1" ] && { echo "(dry-run) stopping before build."; exit 0; }

: "${HU:?}"; : "${HP:?}"
echo "$HP" | docker login "$REGISTRY" -u "$HU" --password-stdin >/dev/null
for svc in "${!want[@]}"; do
  echo "==> build $svc -> ${IMG[$svc]}:$SHA (ctx ${CTX[$svc]})"

  # Handle per-service BuildKit secret if declared
  SECRET_ARG=""
  if [ -n "${SECRET[$svc]:-}" ] && [ -n "${SECRETSRC[$svc]:-}" ]; then
    if [ ! -f "${SECRETSRC[$svc]}" ]; then
      echo "secret file not found for $svc: ${SECRETSRC[$svc]}" >&2
      exit 1
    fi
    SECRET_ARG="--secret id=${SECRET[$svc]},src=${SECRETSRC[$svc]}"
  fi

  # Set DOCKER_BUILDKIT=1 if using secrets; otherwise use standard build
  if [ -n "$SECRET_ARG" ]; then
    DOCKER_BUILDKIT=1 docker build --network=host $SECRET_ARG ${FILE[$svc]:+-f "${FILE[$svc]}"} -t "$REGISTRY/$HARBOR_PROJECT/${IMG[$svc]}:$SHA" "${CTX[$svc]}"
  else
    docker build --network=host ${FILE[$svc]:+-f "${FILE[$svc]}"} -t "$REGISTRY/$HARBOR_PROJECT/${IMG[$svc]}:$SHA" "${CTX[$svc]}"
  fi

  docker push "$REGISTRY/$HARBOR_PROJECT/${IMG[$svc]}:$SHA"
  # Also move a :latest tag so downstream consumers can track the tip if they choose.
  docker tag  "$REGISTRY/$HARBOR_PROJECT/${IMG[$svc]}:$SHA" "$REGISTRY/$HARBOR_PROJECT/${IMG[$svc]}:latest"
  docker push "$REGISTRY/$HARBOR_PROJECT/${IMG[$svc]}:latest"
done
echo "pushed images for: ${!want[*]} @ $SHA"

# Output the comma-separated list of deployed services for downstream use
printf -v deploy_list '%s,' "${!want[@]}"
echo "DEPLOY_LIST=${deploy_list%,}"
