#!/usr/bin/env bash
# Build CCC images, import into k0s on vakr, rollout, verify NodePorts.
set -euo pipefail

: "${SHA:?SHA required}"
: "${DEPLOY_SERVICES:?comma-separated service keys (api, glass)}"

readonly VAKR_SSH="${VAKR_SSH:-vakr-svc}"
readonly NAMESPACE="${CCC_NAMESPACE:-ccc-tmp}"
readonly MANIFEST="${CCC_MANIFEST:-deploy/k0s/ccc.yaml}"
readonly GLASS_URL="${CCC_GLASS_URL:-http://10.10.20.101:30808/}"
readonly API_HEALTH_URL="${CCC_API_HEALTH_URL:-http://10.10.20.101:30800/health}"
readonly NETRC="${FORGEJO_NETRC:-$HOME/services/forge-toolkit/.forgejo-netrc}"
readonly NPM_TOKEN_FILE="${FORGEJO_NPM_TOKEN:-$HOME/services/forge-toolkit/.npm-token}"

log() { printf '==> %s\n' "$*"; }

need_api=0
need_glass=0
IFS=',' read -r -a _svcs <<< "${DEPLOY_SERVICES}"
for raw in "${_svcs[@]}"; do
  svc="${raw// /}"
  [ -n "$svc" ] || continue
  case "$svc" in
    api|api_* ) need_api=1 ;;
    glass|glass_* ) need_glass=1 ;;
    * ) echo "unknown deploy service key: $svc" >&2; exit 1 ;;
  esac
done

build_api() {
  log "build ccc/ultradex:dev @ ${SHA:0:12}"
  local secret_arg=()
  if [ -f "$NETRC" ]; then
    secret_arg=(--secret "id=forgejo_netrc,src=${NETRC}")
  fi
  DOCKER_BUILDKIT=1 docker build --network=host "${secret_arg[@]}" \
    -t ccc/ultradex:dev -f Dockerfile .
}

build_glass() {
  log "build ccc/glass:dev @ ${SHA:0:12}"
  local secret_arg=()
  if [ -f "$NPM_TOKEN_FILE" ]; then
    local npmrc
    npmrc="$(mktemp)"
    {
      echo '@ravenhelm:registry=http://hrafngud.ravenmask.net:3300/api/packages/nate/npm/'
      echo "//hrafngud.ravenmask.net:3300/api/packages/nate/npm/:_authToken=$(cat "$NPM_TOKEN_FILE")"
    } > "$npmrc"
    secret_arg=(--secret "id=npmrc,src=${npmrc}")
    trap 'rm -f "$npmrc"' RETURN
  fi
  DOCKER_BUILDKIT=1 docker build --network=host "${secret_arg[@]}" \
    -t ccc/glass:dev -f apps/web/Dockerfile .
}

import_image() {
  local tag=$1
  log "import ${tag} -> vakr k0s"
  docker save "$tag" | ssh -o ConnectTimeout=15 "$VAKR_SSH" "sudo k0s ctr images import -"
}

k0s() {
  ssh -o ConnectTimeout=15 "$VAKR_SSH" "sudo k0s kubectl -n ${NAMESPACE} $*"
}

rollout() {
  local dep=$1
  log "rollout restart/${dep}"
  k0s rollout restart "deployment/${dep}"
  k0s rollout status "deployment/${dep}" --timeout=240s
}

if [ "$need_api" = 1 ]; then
  build_api
  import_image ccc/ultradex:dev
fi
if [ "$need_glass" = 1 ]; then
  build_glass
  import_image ccc/glass:dev
fi

log "apply manifest ${MANIFEST}"
k0s apply -f - < "$MANIFEST"

if [ "$need_api" = 1 ]; then
  rollout api
  rollout worker
  rollout jobsearch-worker
fi
if [ "$need_glass" = 1 ]; then
  rollout glass
fi

log "verify endpoints"
for i in $(seq 1 20); do
  glass_ok=0 api_ok=0
  if [ "$need_glass" = 1 ]; then
    curl -fsS --connect-timeout 3 --max-time 8 "$GLASS_URL" >/dev/null && glass_ok=1
  else
    glass_ok=1
  fi
  if [ "$need_api" = 1 ]; then
    curl -fsS --connect-timeout 3 --max-time 8 "$API_HEALTH_URL" >/dev/null && api_ok=1
  else
    api_ok=1
  fi
  if [ "$glass_ok" = 1 ] && [ "$api_ok" = 1 ]; then
    log "deploy OK (glass=${need_glass} api=${need_api}) sha=${SHA:0:12}"
    exit 0
  fi
  sleep 6
done
echo "health check failed after rollout" >&2
exit 1
