# Ultradex Baseline and Official Python SDK Implementation Plan

> **For agentic workers:** Execute each task test-first. This is the bounded JS-U01 work unit; do not add job-search persistence, source adapters, generic commands, Go CLI changes, or MCP migration here.

**Goal:** Establish a reproducible Python baseline, return reviewed `control-surface.v1` contract handles from existing asynchronous commands, expose read-only operation lifecycle through GraphQL, and make the official Python SDK the sole supported Python client boundary.

**Architecture:** Existing analyze/sync behavior remains behind the Gateway and ARQ. REST accepts commands and returns a `ContractHandleV1`; GraphQL reads operation state and chronological events; the official SDK submits over REST and reads over GraphQL. The existing database schema is not migrated in this unit: `contract_id` is the stable legacy bridge value `operation_id`. The reviewed `ravenhelm-contracts==0.2.0` Python artifact supplies validation rather than copying the wire shape.

**Tech Stack:** Python 3.11+, FastAPI, Strawberry GraphQL, SQLAlchemy 2, HTTPX, Pydantic 2, ARQ, pytest, setuptools.

## Frozen boundary

- Repository: `nwalker85/ultradex` (GitHub-primary).
- Base: `origin/main` at `c9c9b7cd53c77c6db3ad292d937d6246fa9eff64`.
- Branch/worktree: `feat/jobsearch-observability-foundation` in `/Users/nate/var/worktrees/ultradex-jobsearch-observability`.
- Contract dependency: reviewed `ravenhelm-contracts` 0.2.0 artifact; merge compatibility cannot be claimed until its PR is merged.
- No production cutover or deployed-service replacement.
- Known Go baseline failure in `cli/go.mod` remains JS-U05.
- Existing MCP package collision is recorded as a strict expected failure and remains JS-U06; an unexpected pass fails the test so the deferral cannot become stale.

---

### Task 1: Make the Python baseline honest and reproducible

**Files:**
- Create: `pyproject.toml`
- Create: `pytest.ini`
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_runtime_baseline.py`
- Create: `tests/test_mcp_deferred.py`
- Modify: `requirements.txt`
- Modify: `setup.py`
- Modify: `core/database.py`
- Modify: `api/routes/health.py`
- Modify: `api/main.py`

**Expected RED:** API dependencies yield a `Database` wrapper instead of a SQLAlchemy session; SQLAlchemy 2 rejects raw health SQL; ARQ pool construction is invalid; GraphQL is absent; packaging is not buildable; MCP import fails because local `mcp` shadows the external package.

- [x] Add hermetic SQLite fixtures and a real `Session`-yielding FastAPI dependency.
- [x] Use SQLAlchemy `text()` for readiness probes.
- [x] Construct ARQ with `RedisSettings`.
- [x] Package the official typed `ultradex_sdk` namespace plus the typed `sdk` compatibility namespace, require Python 3.11+, and remove deprecated GitLab/invalid Python CLI metadata.
- [x] Declare Strawberry, build, pytest, and the reviewed contract dependency.
- [x] Configure pytest to collect `tests/`; keep the MCP defect visible as one strict, reasoned XFAIL subprocess check.
- [x] Run focused baseline tests and record the separate Go failure without relabeling it green.

### Task 2: Return a canonical handle from command acceptance

**Files:**
- Modify: `core/models.py`
- Modify: `core/operation_service.py`
- Modify: `api/routes/v2/commands.py`
- Create: `tests/test_command_acceptance.py`

**Expected RED:** command routes expose query-only parameters, ignore idempotency/correlation/actor headers, and return legacy `OperationResponse` rather than a contract handle.

- [x] Build responses with the shared `ContractHandleV1` binding and embed its packaged JSON Schema in OpenAPI.
- [x] Return canonical `accepted` without changing legacy stored operation statuses.
- [x] Accept JSON bodies while preserving the legacy query `limit` bridge.
- [x] Forward idempotency, correlation, and delegation context to `CommandRequest`; derive actor identity from the bearer credential.
- [x] Prove repeated, concurrent, conflicting, and expired idempotency behavior without duplicate enqueue or orphan operations.
- [x] Validate every command response through the shared Python contract binding.

### Task 3: Modernize and mount read-only GraphQL operation lifecycle

**Files:**
- Modify: `api/graphql/schema.py`
- Modify: `api/graphql/__init__.py`
- Modify: `api/main.py`
- Create: `tests/test_graphql_operations.py`

**Expected RED:** `strawberry.JSON` no longer exists; SQLAlchemy `Session` arguments are treated as GraphQL inputs; the app has no GraphQL route.

- [x] Use `strawberry.scalars.JSON` and `Info.context["db"]`.
- [x] Return operation detail/list plus bounded, cursor-based chronological lifecycle event pages without N+1 queries.
- [x] Return honest nullable freshness until JS-U02 adds a durable projection checkpoint; do not fabricate source position, lag, or `fresh` status.
- [x] Mount `GraphQLRouter` at `/api/graphql` with a session-bearing context dependency.
- [x] Prove the schema has no mutation root and the mounted route receives its database dependency.

### Task 4: Make the official Python SDK typed and handle-first

**Files:**
- Modify: `sdk/ultradex_sdk.py`
- Modify: `sdk/__init__.py`
- Modify: `SDK_README.md`
- Create: `tests/test_sdk.py`

**Expected RED:** SDK methods return dictionaries, submit the wrong request shape, assume `id`, poll immediately, and use REST for reads.

- [x] Add `submit_analyze_contacts()` and `submit_sync_contacts()` returning `ContractHandleV1` immediately.
- [x] Preserve bearer authorization, idempotency, delegation, and correlation headers; derive actor identity server-side.
- [x] Preserve governed failed contract handles returned at `503` instead of discarding them as generic HTTP errors.
- [x] Query operation lifecycle/events through GraphQL and surface GraphQL errors explicitly.
- [x] Keep legacy `analyze_contacts()` / `sync_contacts()` wrappers by composing submit plus wait; acceptance never masquerades as completion.
- [x] Accept an injected HTTPX transport for hermetic tests.
- [x] Treat legacy completion plus `succeeded`, `failed`, `cancelled`, `expired`, `revoked`, `refused`, and `unverifiable` as terminal.

### Task 5: Verify and publish JS-U01

- [x] `pytest -q` passes: 43 tests plus exactly one documented strict MCP XFAIL.
- [x] `python -m compileall -q api core sdk tests` passes.
- [x] `python -m build` produces an SDK-only wheel and sdist.
- [x] Wheel inspection and an out-of-tree import check confirm current `ultradex_sdk`, compatible `sdk`, and metadata, with no `mcp`, `api`, `core`, or CLI package.
- [x] `git diff --check origin/main...HEAD` passes.
- [x] Independent review reports findings first and clears the unit.
- [x] Push branch and open GitHub PR 2; do not merge without PR-specific approval.
