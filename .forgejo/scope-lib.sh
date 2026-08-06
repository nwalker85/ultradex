#!/usr/bin/env bash
# scope-lib.sh — shared change-scoping for Profile A (deploy) and B (build).
# Generalises heimdall's hardcoded case-statement into a data-driven loop keyed
# off a per-repo service map. Sourced by deploy-on-host.sh / build-on-host.sh.
#
# The service map (associative arrays IMG / CTX / PREFIX / FILE) is defined by the repo's
# .forgejo/services.map if present, else a single-service default derived from $REPO.
# The service whose PREFIX is empty is the "catch-all" (heimdall's `web`): any changed
# path not owned by another service's PREFIX, and not on the non-deployable skip list,
# maps to it.

# Non-deployable paths never trigger a build/deploy (docs, tests, CI config).
scope_is_skippable() {
  case "$1" in
    docs/*|*.md|e2e/*|.forgejo/*|.github/*|*.test.*|*.spec.*|*/__tests__/*) return 0 ;;
    *) return 1 ;;
  esac
}

# load_service_map — populate IMG / CTX / PREFIX / FILE from .forgejo/services.map or a default.
# Optionally populates SECRET / SECRETSRC if declared and defined in services.map.
# Requires REPO to be set. Expects the caller to `declare -A IMG CTX PREFIX FILE` first,
# and optionally `declare -A SECRET SECRETSRC` for per-service BuildKit secret support.
load_service_map() {
  : "${REPO:?REPO must be set before load_service_map}"
  if [ -f .forgejo/services.map ]; then
    # shellcheck source=/dev/null
    source .forgejo/services.map
  else
    # Default: one image built from repo root, catch-all for every source change.
    IMG[web]="${REPO}-web"; CTX[web]="."; PREFIX[web]=""; FILE[web]="Dockerfile"
  fi
  [ "${#IMG[@]}" -gt 0 ] || { echo "service map is empty" >&2; return 1; }
}

# compute_scope <want-array-name> <baseline-ref>
#   Populates the named associative array with services that must be acted on.
#   FORCE_SERVICES (comma list) overrides change detection.
#   baseline-ref empty / unusable => FULL scope (build everything). For A pass the
#   deployed SHA; for B pass HEAD~1 (the merge delta).
compute_scope() {
  local -n _want="$1"; local baseline="$2"
  local s f matched catchall=""

  if [ -n "${FORCE_SERVICES:-}" ]; then
    echo "scope: explicit FORCE_SERVICES=$FORCE_SERVICES"
    for s in ${FORCE_SERVICES//,/ }; do
      [ -n "${IMG[$s]:-}" ] || { echo "unknown service: $s" >&2; exit 1; }
      _want["$s"]=1
    done
    return 0
  fi

  local -a CHANGED
  if [ -n "$baseline" ] && git cat-file -e "${baseline}^{commit}" 2>/dev/null \
       && git merge-base --is-ancestor "$baseline" HEAD 2>/dev/null; then
    mapfile -t CHANGED < <(git diff --name-only "$baseline" HEAD)
    echo "scope: ${#CHANGED[@]} files changed since $baseline"
  else
    mapfile -t CHANGED < <(git ls-files)
    echo "scope: FULL (no usable baseline)"
  fi

  for s in "${!PREFIX[@]}"; do [ -z "${PREFIX[$s]}" ] && catchall="$s"; done

  for f in "${CHANGED[@]}"; do
    scope_is_skippable "$f" && continue
    matched=""
    for s in "${!PREFIX[@]}"; do
      [ -n "${PREFIX[$s]}" ] || continue
      case "$f" in "${PREFIX[$s]}"*) matched="$s"; break ;; esac
    done
    if [ -n "$matched" ]; then _want["$matched"]=1
    elif [ -n "$catchall" ]; then _want["$catchall"]=1
    fi
  done
}
