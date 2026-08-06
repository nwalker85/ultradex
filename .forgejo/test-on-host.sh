#!/usr/bin/env bash
set -euo pipefail
# Sovereign CI host-side step (runs as ravenmask@hrafngud, cwd = repo clone @ PR head).
# Generalised from heimdall's test-on-host.sh. Fail-fast (set -e) so any red test
# blocks the merge — that is the whole point of the gate.
#
# Supports npm, pnpm, and Python repositories. Also supports monorepos with no root
# manifest but multiple services declared in .forgejo/services.map.
#
# Dependency caching: For npm: node_modules comes from a cached "deps image" keyed by
# the package-lock.json hash, tagged <repo>[-<service>]-ci-deps:<hash>. For Python:
# site-packages is cached similarly, keyed by uv.lock / pyproject.toml / requirements.txt.
#
# Env: REPO (image-tag namespace; defaults to the clone dir name).
REPO="${REPO:-$(basename "$PWD")}"

# === STACK DETECTION ===
if [ -f package.json ]; then
  STACK="npm"
elif [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  STACK="python"
else
  STACK="unrecognized"
fi

# === NPM GATE ===
npm_gate() {
  [ -f package-lock.json ] || { echo "no package-lock.json — this template assumes an npm repo; adjust test-on-host.sh for other stacks" >&2; exit 1; }

  CACHE_TAG=$(sha256sum package-lock.json | awk '{print $1}' | cut -c1-16)
  DEPS_IMG="${REPO}${SERVICE_SLUG:+-$SERVICE_SLUG}-ci-deps:${CACHE_TAG}"

  # Only pull the integration DB image if the repo actually has integration tests.
  HAS_INTEGRATION=0
  if grep -q '"test:integration"' package.json 2>/dev/null; then
    HAS_INTEGRATION=1
    docker pull -q postgres:16 >/dev/null || true
  fi

  if docker image inspect "$DEPS_IMG" >/dev/null 2>&1; then
    echo "deps cache HIT ($CACHE_TAG)"
  else
    echo "deps cache MISS ($CACHE_TAG) — running npm ci once"
    # Private @ravenhelm/* deps resolve from the Forgejo npm registry. Inject the
    # package token as a BuildKit secret so it never lands in an image layer.
    NPMRC_CI=""; SECRET_ARG=""
    if [ -f "$HOME/services/forge-toolkit/.npm-token" ]; then
      NPMRC_CI=$(mktemp)
      { echo "@ravenhelm:registry=http://hrafngud.ravenmask.net:3300/api/packages/nate/npm/"
        echo "//hrafngud.ravenmask.net:3300/api/packages/nate/npm/:_authToken=$(cat "$HOME/services/forge-toolkit/.npm-token")"
      } > "$NPMRC_CI"
      SECRET_ARG="--secret id=npmrc,src=$NPMRC_CI"
    fi
    DOCKER_BUILDKIT=1 docker build -q -t "$DEPS_IMG" $SECRET_ARG -f - . >/dev/null <<'DOCKER'
FROM node:22
WORKDIR /work
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc,required=false npm ci --ignore-scripts --no-audit --no-fund
DOCKER
    [ -n "$NPMRC_CI" ] && rm -f "$NPMRC_CI"
  fi

  docker run --rm --network=host \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$PWD":/work -v /work/node_modules -w /work \
    -e TESTCONTAINERS_HOST_OVERRIDE=localhost -e CI=true -e HAS_INTEGRATION="$HAS_INTEGRATION" \
    "$DEPS_IMG" bash -ceu '
      [ -n "$(ls -A node_modules 2>/dev/null)" ] || { echo "node_modules not initialised from deps image" >&2; exit 1; }
      TEST_SCRIPT="$(npm pkg get scripts.test)"
      if echo "$TEST_SCRIPT" | grep -qiE "playwright|cypress"; then
        # `test` is an E2E runner — needs browsers + a live app (baseURL), so it is a
        # post-deploy smoke suite, NOT a pre-merge unit gate. Build (typecheck+compile) is
        # the gate; the E2E smoke tests run against the deployment.
        echo "::: test script is E2E ($TEST_SCRIPT) — build is the gate; E2E runs post-deploy :::"
        if [ "$(npm pkg get scripts.build)" != "{}" ]; then npm run build; else echo "(no build script — NO-OP)"; fi
      elif [ "$TEST_SCRIPT" != "{}" ]; then
        echo "::: unit :::"; npm test
      elif [ "$(npm pkg get scripts.build)" != "{}" ]; then
        echo "::: no test script — using build as the gate :::"; npm run build
      else
        echo "::: no test or build script — gate is a NO-OP (add a test or build) :::"
      fi
      if [ "$HAS_INTEGRATION" = 1 ]; then
        echo "::: integration :::"; npm run test:integration
      else
        echo "::: integration ::: (none — no test:integration script)"
      fi
    '
}

# === PNPM GATE ===
pnpm_gate() {
  # Cache key from pnpm-lock.yaml hash plus a revision marker; bump PNPMGATE_REV
  # when the install recipe changes to force a deps image rebuild.
  PNPMGATE_REV=1
  CACHE_TAG=$(printf 'pnpmgate%s\n%s' "$PNPMGATE_REV" "$(cat pnpm-lock.yaml)" | sha256sum | awk '{print $1}' | cut -c1-16)
  DEPS_IMG="${REPO}${SERVICE_SLUG:+-$SERVICE_SLUG}-ci-deps:${CACHE_TAG}"

  if docker image inspect "$DEPS_IMG" >/dev/null 2>&1; then
    echo "deps cache HIT ($CACHE_TAG)"
  else
    echo "deps cache MISS ($CACHE_TAG) — building pnpm deps image"
    # Private @ravenhelm/* deps resolve from the Forgejo npm registry. Inject the
    # package token as a BuildKit secret so it never lands in an image layer.
    NPMRC_CI=""; SECRET_ARG=""
    if [ -f "$HOME/services/forge-toolkit/.npm-token" ]; then
      NPMRC_CI=$(mktemp)
      { echo "@ravenhelm:registry=http://hrafngud.ravenmask.net:3300/api/packages/nate/npm/"
        echo "//hrafngud.ravenmask.net:3300/api/packages/nate/npm/:_authToken=$(cat "$HOME/services/forge-toolkit/.npm-token")"
      } > "$NPMRC_CI"
      SECRET_ARG="--secret id=npmrc,src=$NPMRC_CI"
    fi
    DOCKER_BUILDKIT=1 docker build -q -t "$DEPS_IMG" $SECRET_ARG -f - . >/dev/null <<'DOCKER'
FROM node:22
WORKDIR /work
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && \
    PNPM_VERSION=$(grep -oP 'pnpm@\K[0-9.]+' package.json 2>/dev/null || echo "9.15.4") && \
    corepack prepare pnpm@${PNPM_VERSION} --activate
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc,required=false pnpm install --frozen-lockfile
DOCKER
    [ -n "$NPMRC_CI" ] && rm -f "$NPMRC_CI"
  fi

  docker run --rm --network=host \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$PWD":/work -v /work/node_modules -w /work \
    -e CI=true \
    "$DEPS_IMG" bash -ceu '
      [ -n "$(ls -A node_modules 2>/dev/null)" ] || { echo "node_modules not initialised from deps image" >&2; exit 1; }
      TEST_SCRIPT="$(pnpm pkg get scripts.test)"
      if echo "$TEST_SCRIPT" | grep -qiE "playwright|cypress"; then
        # E2E runner (browsers + live baseURL) = post-deploy smoke, not a pre-merge gate.
        echo "::: test script is E2E ($TEST_SCRIPT) — build is the gate; E2E runs post-deploy :::"
        if [ "$(pnpm pkg get scripts.build)" != "{}" ]; then pnpm run build; else echo "(no build script — NO-OP)"; fi
      elif [ "$TEST_SCRIPT" != "{}" ]; then
        echo "::: unit :::"; pnpm test
      elif [ "$(pnpm pkg get scripts.build)" != "{}" ]; then
        echo "::: no test script — using build as the gate :::"; pnpm run build
      else
        echo "::: no test or build script — gate is a NO-OP (add a test or build) :::"
      fi
      # Only lint when an ESLint config actually exists. Otherwise `next lint` drops into
      # an interactive "configure ESLint?" prompt that hangs/fails in CI — and Next.js
      # already runs ESLint during `next build` when a config is present, so build is the gate.
      if [ "$(pnpm pkg get scripts.lint)" != "{}" ] && ls .eslintrc* eslint.config.* >/dev/null 2>&1; then
        echo "::: lint :::"; pnpm run lint
      else
        echo "::: lint skipped (no eslint config — build already lints when configured) :::"
      fi
    '
}

# === PYTHON GATE ===
python_gate() {
  # Cache key from the strongest available lock/manifest.
  LOCKFILE=""
  for f in uv.lock pyproject.toml requirements.txt; do [ -f "$f" ] && { LOCKFILE="$f"; break; }; done
  [ -n "$LOCKFILE" ] || { echo "no uv.lock / pyproject.toml / requirements.txt — not a python repo" >&2; exit 1; }

  # Bump PYGATE_REV whenever the deps-install recipe below changes: the cache tag is
  # otherwise keyed only by the lockfile, so a changed install would silently reuse a
  # stale deps image. Rotating REV forces a rebuild.
  PYGATE_REV=8
  CACHE_TAG=$(printf 'pygate%s\n%s' "$PYGATE_REV" "$(cat "$LOCKFILE")" | sha256sum | awk '{print $1}' | cut -c1-16)
  DEPS_IMG="${REPO}${SERVICE_SLUG:+-$SERVICE_SLUG}-ci-deps:${CACHE_TAG}"

  NETRC_SRC="$HOME/services/forge-toolkit/.forgejo-netrc"
  if grep -qE 'ravenhelm-contracts|mimir-sdk' requirements.txt pyproject.toml 2>/dev/null && [ ! -f "$NETRC_SRC" ]; then
    echo "Forgejo PyPI deps declared but $NETRC_SRC missing — stage netrc on hrafngud (see forge-toolkit .forgejo-netrc)" >&2
    exit 1
  fi

  if docker image inspect "$DEPS_IMG" >/dev/null 2>&1; then
    echo "deps cache HIT ($CACHE_TAG)"
  else
    echo "deps cache MISS ($CACHE_TAG) — building python deps image"
    # Install into the SYSTEM interpreter (not a project .venv) so deps survive the
    # repo bind-mount over /work at test time — mirrors how the npm gate keeps
    # node_modules. Only manifests are copied (globbed, so a missing one is skipped);
    # the full source is bind-mounted at run time, so `-e .` resolves against it.
    # Sovereign PyPI: if a Forgejo PyPI netrc is staged on the host, mount it as a build
    # secret and point pip/uv at the Forgejo index so private deps (e.g. ravenhelm-contracts) resolve.
    PY_SECRET_ARG=""; PIP_INDEX=""
    if [ -f "$NETRC_SRC" ]; then
      PY_SECRET_ARG="--secret id=netrc,src=$NETRC_SRC"
      PIP_INDEX="--extra-index-url http://hrafngud.ravenmask.net:3300/api/packages/nate/pypi/simple/ --trusted-host hrafngud.ravenmask.net"
    fi
    # shellcheck disable=SC2086
    # --network=host + --add-host so the build container resolves the Forgejo FQDN (MagicDNS
    # is unavailable in the default build network; Forgejo PyPI URLs use the ROOT_URL FQDN).
    DOCKER_BUILDKIT=1 docker build -q -t "$DEPS_IMG" --network=host $PY_SECRET_ARG --build-arg PIP_INDEX="$PIP_INDEX" -f - . >/dev/null <<'DOCKER'
FROM python:3.12-slim
WORKDIR /work
ARG PIP_INDEX=""
RUN pip install -q uv
COPY uv.lock* pyproject.toml* requirements.txt* ./
# Install DECLARED deps directly (src/-layout can't `-e .` without the source, which is
# bind-mounted at run). $PIP_INDEX + the mounted netrc let private Forgejo-PyPI deps resolve.
# A failed deps install FAILS the build (fi && …), instead of silently reaching pytest.
RUN --mount=type=secret,id=netrc,target=/root/.netrc,required=false \
    if [ -f pyproject.toml ]; then \
      python3 -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'));p=d.get('project',{});deps=list(p.get('dependencies',[]));[deps.extend(v) for v in p.get('optional-dependencies',{}).values()];[deps.extend([x for x in v if isinstance(x,str)]) for v in d.get('dependency-groups',{}).values()];deps.extend(d.get('tool',{}).get('uv',{}).get('dev-dependencies',[]));open('/tmp/deps.txt','w').write(chr(10).join(deps))"; \
      if [ -s /tmp/deps.txt ]; then uv pip install --system $PIP_INDEX -r /tmp/deps.txt; fi; \
      if [ -f requirements.txt ]; then uv pip install --system $PIP_INDEX -r requirements.txt; fi; \
    elif [ -f requirements.txt ]; then \
      uv pip install --system $PIP_INDEX -r requirements.txt ; \
    fi && \
    uv pip install --system pytest pytest-asyncio build wheel setuptools
DOCKER
  fi

  # Repo mounted over /work; deps come from the image's system site-packages.
  docker run --rm --network=host \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$PWD":/work -w /work \
    -e CI=true \
    "$DEPS_IMG" bash -ceu '
      # Deps are baked into the image, but the editable project link was made at build
      # time without the source. Re-establish it against the now-mounted source
      # (--no-deps = fast, deps already present) so the package imports regardless of
      # src/ or flat layout.
      [ -f pyproject.toml ] && uv pip install --system -e . --no-deps -q 2>/dev/null || true
      if [ -d tests ] || [ -d test ] || ls test_*.py *_test.py >/dev/null 2>&1; then
        echo "::: unit :::"
        rc=0; python -m pytest -q || rc=$?
        # 0 = pass, 5 = no tests collected (no-op); anything else fails the gate.
        [ "$rc" = 0 ] || [ "$rc" = 5 ] || exit "$rc"
        if [ "$rc" = 5 ]; then echo "::: pytest collected no tests — no-op :::"; fi
      else
        echo "::: no tests — gate is a NO-OP (add tests) :::"
      fi
    '
}

# === ULTRADEX: TypeScript SDK + Obsidian plugin (optional, skip if absent) ===
ultradex_npm_project_gate() {
  local rel="$1" slug="$2"
  local proj_root="$PWD/$rel"
  [ -f "$proj_root/package.json" ] || return 0

  CACHE_TAG=$(printf 'ultranpm%s\n' "$(cat "$proj_root/package.json")" | sha256sum | awk '{print $1}' | cut -c1-16)
  DEPS_IMG="${REPO}-${slug}-ci-deps:${CACHE_TAG}"

  if docker image inspect "$DEPS_IMG" >/dev/null 2>&1; then
    echo "deps cache HIT ($CACHE_TAG)"
  else
    echo "deps cache MISS ($CACHE_TAG) — npm install"
    NPMRC_CI=""; SECRET_ARG=""
    if [ -f "$HOME/services/forge-toolkit/.npm-token" ]; then
      NPMRC_CI=$(mktemp)
      { echo "@ravenhelm:registry=http://hrafngud.ravenmask.net:3300/api/packages/nate/npm/"
        echo "//hrafngud.ravenmask.net:3300/api/packages/nate/npm/:_authToken=$(cat "$HOME/services/forge-toolkit/.npm-token")"
      } > "$NPMRC_CI"
      SECRET_ARG="--secret id=npmrc,src=$NPMRC_CI"
    fi
    DOCKER_BUILDKIT=1 docker build -q -t "$DEPS_IMG" $SECRET_ARG -f - "$proj_root" >/dev/null <<'DOCKER'
FROM node:22
WORKDIR /work
COPY package.json ./
COPY package-lock.json* pnpm-lock.yaml* ./
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc,required=false \
    if [ -f package-lock.json ]; then npm ci --ignore-scripts --no-audit --no-fund; else npm install --ignore-scripts --no-audit --no-fund; fi
DOCKER
    [ -n "$NPMRC_CI" ] && rm -f "$NPMRC_CI"
  fi

  docker run --rm --network=host \
    -v "$proj_root":/work -v /work/node_modules -w /work \
    -e CI=true \
    "$DEPS_IMG" bash -ceu '
      [ -n "$(ls -A node_modules 2>/dev/null)" ] || { echo "node_modules not initialised" >&2; exit 1; }
      if [ "$(npm pkg get scripts.build)" != "{}" ]; then echo "::: build :::"; npm run build; fi
      if [ "$(npm pkg get scripts.test)" != "{}" ]; then echo "::: unit :::"; npm test; else echo "::: no test script :::"; fi
    '
}

ultradex_ts_gates() {
  local repo_root="$1"
  cd "$repo_root" || exit 1

  if [ -f sdk/typescript/package.json ]; then
    echo ""
    echo "=== ultradex: sdk/typescript ==="
    ultradex_npm_project_gate "sdk/typescript" "sdk"
  else
    echo "::: sdk/typescript absent — skip :::"
  fi

  if [ -f integrations/obsidian-ultradex/package.json ]; then
    echo ""
    echo "=== ultradex: obsidian plugin ==="
    if [ ! -f sdk/typescript/package.json ]; then
      echo "plugin present but sdk/typescript missing — cannot resolve @ultradex/sdk" >&2
      exit 1
    fi
    PLUGIN_DIR="$repo_root/integrations/obsidian-ultradex"
    SDK_DIR="$repo_root/sdk/typescript"
    docker run --rm --network=host \
      -v "$SDK_DIR":/sdk -v "$PLUGIN_DIR":/work -w /work \
      -e CI=true \
      node:22 bash -ceu '
        cd /sdk
        npm install --ignore-scripts --no-audit --no-fund
        npm run build
        cd /work
        npm install --ignore-scripts --no-audit --no-fund "file:/sdk"
        echo "::: unit :::"; npm test
      '
  else
    echo "::: obsidian plugin absent — skip :::"
  fi
}

# === DISPATCH ===
case "$STACK" in
  npm)
    SERVICE_SLUG="" # Single-repo: no suffix
    if [ -f pnpm-lock.yaml ] && [ ! -f package-lock.json ]; then
      pnpm_gate
    else
      npm_gate
    fi
    ;;
  python)
    SERVICE_SLUG="" # Single-repo: no suffix
    python_gate
    ultradex_ts_gates "$PWD"
    ;;
  *)
    # No root manifest: check for monorepo services.map
    if [ -f .forgejo/services.map ]; then
      echo "no root manifest — attempting monorepo mode"

      # Declare ALL arrays a service map may set (incl. the optional per-service build
      # secret) BEFORE sourcing — else SECRET[key]/SECRETSRC[key] become indexed-array
      # assignments and the string key is evaluated as arithmetic ("key: unbound variable").
      declare -A IMG CTX PREFIX FILE SECRET SECRETSRC
      # shellcheck source=/dev/null
      source .forgejo/services.map

      # Collect distinct CTX dirs
      declare -a CTXS=()
      for svc in "${!CTX[@]}"; do
        ctx="${CTX[$svc]}"
        # Avoid duplicates
        if [[ ! " ${CTXS[@]} " =~ " ${ctx} " ]]; then
          CTXS+=("$ctx")
        fi
      done

      if [ "${#CTXS[@]}" -eq 0 ]; then
        echo "service map found but no CTX dirs — gate is a no-op"
        exit 0
      fi

      # Run gates for each distinct service context
      REPO_ROOT="$PWD"
      for ctx in "${CTXS[@]}"; do
        # Convert ctx path to a service slug for DEPS_IMG (e.g., ./api → api, . → root)
        if [ "$ctx" = "." ]; then
          SERVICE_SLUG=""
        else
          SERVICE_SLUG=$(echo "$ctx" | sed 's|./||; s|/|-|g')
        fi

        echo ""
        echo "=== service: $ctx (slug: ${SERVICE_SLUG:-root}) ==="
        cd "$REPO_ROOT/$ctx" || { echo "failed to cd to $ctx" >&2; exit 1; }

        # Detect stack in this service dir
        local_stack="unrecognized"
        if [ -f package.json ]; then
          local_stack="npm"
        elif [ -f pyproject.toml ] || [ -f requirements.txt ]; then
          local_stack="python"
        fi

        case "$local_stack" in
          npm)
            if [ -f pnpm-lock.yaml ] && [ ! -f package-lock.json ]; then
              pnpm_gate
            else
              npm_gate
            fi
            ;;
          python)
            python_gate
            ;;
          *)
            echo "  (service stack unrecognized — skipped)"
            ;;
        esac

        cd "$REPO_ROOT" || { echo "failed to return to repo root" >&2; exit 1; }
      done

      echo ""
      echo "monorepo gate complete"
    else
      echo "unrecognized stack (no package.json / pyproject.toml / requirements.txt, and no .forgejo/services.map) — gate is a no-op"
      exit 0
    fi
    ;;
esac
