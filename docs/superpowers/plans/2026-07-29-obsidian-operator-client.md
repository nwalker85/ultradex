# Ultradex Obsidian Operator Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and follow strict TDD task by task. Read
> `test-driven-development/writing-good-tests.md` before changing tests.

**Goal:** Deliver a mutation-aware Obsidian operator console backed exclusively
by the official Ultradex TypeScript SDK, with a sanitized local end-to-end proof.

**Architecture:** Stack this work on the canonical JS-U03 governed-command
branch. Add a scoped `{read, command}` credential, a transport-agnostic
TypeScript SDK, and an Obsidian adapter/view. The plugin treats
`ContractHandleV1`, lifecycle events, approvals, refusals, unverifiable outcomes,
and receipts as operator state. A validated aggregate snapshot fails closed.

**Tech stack:** Python 3.11+, FastAPI, pytest, TypeScript, Vitest, esbuild,
Obsidian Plugin API, Docker Compose, NATS JetStream, PostgreSQL, Redis.

**Design:** `docs/superpowers/specs/2026-07-29-obsidian-operator-client-design.md`

## Frozen delivery boundaries

- Canonical remote: private Forgejo `nate/ultradex`.
- GitHub is a passive mirror and not a review or CI gate.
- Use dedicated worktrees and stacked branches.
- Do not merge any PR.
- Do not replace the deployed service architecture.
- Do not add real career/contact/message content to tests, logs, or agent context.
- Do not install in the working vault before the separate test vault passes.
- Do not use a full operator/delegation-admin token in Obsidian.
- Node package builds and tests are allowed; no raw Node development server is
  required. If a persistent Node process becomes necessary, use PM2.

---

### Task 1: Add a scoped career-operator credential

**Files:**

- Modify: `api/auth.py`
- Modify: `api/main.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `tests/test_auth_boundary.py`
- Modify: `tests/test_runtime_baseline.py`

- [ ] Write failing tests proving `ULTRADEX_COMMAND_TOKEN` authenticates with
  exactly `read` and `command`, cannot access delegation administration, and
  a partially configured token/ID pair fails startup. The pair is optional when
  neither variable is set so existing deployments remain compatible.
- [ ] Prove the existing read-only and full operator credentials retain their
  current scopes.
- [ ] Implement the paired command credential without a default or source secret.
- [ ] Wire only environment references through Compose and document custody.
- [ ] Run:
  `python -m pytest tests/test_auth_boundary.py tests/test_runtime_baseline.py -q`.
- [ ] Commit: `feat: add scoped career operator credential`.

### Task 2: Establish the TypeScript SDK package and transport

**Files:**

- Create: `package.json`
- Create: `sdk/typescript/package.json`
- Create: `sdk/typescript/tsconfig.json`
- Create: `sdk/typescript/src/index.ts`
- Create: `sdk/typescript/src/contracts.ts`
- Create: `sdk/typescript/src/transport.ts`
- Create: `sdk/typescript/src/client.ts`
- Create: `sdk/typescript/tests/client.test.ts`
- Create: `sdk/typescript/tests/fixtures.ts`

- [ ] Write failing request-contract tests with literal expectations for bearer
  headers, canonical endpoint paths, GraphQL payloads, and structured errors.
- [ ] Create a private root npm workspace and lockfile. Publishable SDK package
  identity is `@ultradex/sdk` version `0.1.0`, ESM, with Node `>=20`.
- [ ] Pin TypeScript `5.9.3`, Vitest `3.2.6`, and Zod `4.1.5`; do not adopt the
  unproven TypeScript 7 toolchain during this delivery.
- [ ] Define complete TypeScript types and runtime guards for projections,
  operations, lifecycle events, and `ContractHandle`.
- [ ] Implement an injected `UltradexTransport`; do not depend on Node or Obsidian.
- [ ] Implement typed `getHealth()` and `getReadiness()` methods as the first
  public client behaviors. Keep low-level REST/GraphQL execution private; do not
  expose a raw API escape hatch.
- [ ] Implement authentication, JSON, GraphQL-error, timeout, and schema error
  mapping without flattening governed handles.
- [ ] Export only the stable public client, input, output, and error types.
- [ ] Run: `npm test --workspace @ultradex/sdk`.
- [ ] Run: `npm run build --workspace @ultradex/sdk`.
- [ ] Commit: `feat: add official TypeScript SDK transport`.

### Task 3: Expose and type projection, approval, and receipt reads

**Files:**

- Modify: `core/jobsearch_projections.py`
- Modify: `api/graphql/jobsearch_types.py`
- Modify: `api/graphql/schema.py`
- Modify: `tests/test_jobsearch_projection_repository.py`
- Modify: `tests/test_graphql_jobsearch.py`
- Modify: `sdk/typescript/src/contracts.ts`
- Modify: `sdk/typescript/src/client.ts`
- Create: `sdk/typescript/src/jobsearch-queries.ts`
- Modify: `sdk/typescript/src/index.ts`
- Modify: `sdk/typescript/tests/client.test.ts`
- Create: `sdk/typescript/tests/projections.test.ts`

- [ ] Write failing tests for opportunities, applications, relationships,
  outreach, operations, bounded lifecycle events, exact approval evidence, and
  one execution receipt resolved by operation ID.
- [ ] Add read-scoped GraphQL fields `approval(id: String!)` and
  `executionReceipt(operationId: String!)`. Return contract-backed types with
  complete approval bindings and receipt payload/hash; never expose secret
  signing material.
- [ ] Preserve the proof boundary: a receipt read is `server-recorded`, not
  `signature-verified`. The API does not claim signature verification without a
  trusted public-key registry.
- [ ] Use SDK-owned GraphQL documents; callers provide typed filters only.
- [ ] Preserve page freshness and cursor values exactly.
- [ ] Reject incomplete pages, malformed terminal states, and malformed
  approval/receipt evidence.
- [ ] Run:
  `python -m pytest tests/test_jobsearch_projection_repository.py tests/test_graphql_jobsearch.py -q`.
- [ ] Run SDK test and build commands from Task 2.
- [ ] Commit: `feat: expose typed job-search evidence reads`.

### Task 4: Add the closed governed-command catalog

**Files:**

- Create: `sdk/typescript/src/jobsearch-commands.ts`
- Modify: `sdk/typescript/src/contracts.ts`
- Modify: `sdk/typescript/src/client.ts`
- Modify: `sdk/typescript/src/index.ts`
- Create: `sdk/typescript/tests/commands.test.ts`

- [ ] Write failing tests for all nine command names and their literal parameter
  payloads.
- [ ] Require a non-empty idempotency key and preserve optional correlation and
  delegation headers.
- [ ] Prove no actor header or server-owned correlation context is sent.
- [ ] Return a validated governed handle for HTTP 202 and 503 responses.
- [ ] Keep HTTP 401/403/409/422 as structured client errors because intent was
  not accepted.
- [ ] Run SDK test and build commands from Task 2.
- [ ] Commit: `feat: add governed job-search commands to TypeScript SDK`.

### Task 5: Scaffold the Obsidian plugin and secure settings

**Files:**

- Create: `integrations/obsidian-ultradex/manifest.json`
- Create: `integrations/obsidian-ultradex/versions.json`
- Create: `integrations/obsidian-ultradex/package.json`
- Create: `integrations/obsidian-ultradex/tsconfig.json`
- Create: `integrations/obsidian-ultradex/esbuild.config.mjs`
- Create: `integrations/obsidian-ultradex/styles.css`
- Create: `integrations/obsidian-ultradex/src/main.ts`
- Create: `integrations/obsidian-ultradex/src/settings.ts`
- Create: `integrations/obsidian-ultradex/src/obsidian-transport.ts`
- Create: `integrations/obsidian-ultradex/tests/settings.test.ts`
- Create: `integrations/obsidian-ultradex/tests/obsidian-transport.test.ts`

- [ ] Write failing tests proving the token is never saved in ordinary plugin
  data and network calls refuse when SecretStorage is unavailable.
- [ ] Store only base URL, refresh interval, view filters, secret key reference,
  and UI preferences in plugin data.
- [ ] Pin the Obsidian API development dependency to `1.11.4` and set
  `minAppVersion` to `1.11.4`; SecretStorage first appears in that API. The local
  app verified for this delivery is `1.11.7`.
- [ ] Implement an SDK transport using Obsidian `requestUrl`.
- [ ] Register lightweight commands on load and defer the view until first use.
- [ ] Run: `npm test --workspace obsidian-ultradex`.
- [ ] Run: `npm run build --workspace obsidian-ultradex`.
- [ ] Commit: `feat: scaffold secure Ultradex Obsidian plugin`.

### Task 6: Build the atomic projection store and monitor view

**Files:**

- Create: `integrations/obsidian-ultradex/src/projection-store.ts`
- Create: `integrations/obsidian-ultradex/src/views/monitor-view.ts`
- Create: `integrations/obsidian-ultradex/src/components/freshness-badge.ts`
- Create: `integrations/obsidian-ultradex/src/components/contract-state.ts`
- Create: `integrations/obsidian-ultradex/src/sanitize.ts`
- Modify: `integrations/obsidian-ultradex/src/main.ts`
- Modify: `integrations/obsidian-ultradex/styles.css`
- Create: `integrations/obsidian-ultradex/tests/projection-store.test.ts`
- Create: `integrations/obsidian-ultradex/tests/monitor-view.test.ts`

- [ ] Write failing tests proving a partial refresh never replaces the last valid
  aggregate snapshot and concurrent refreshes share one request.
- [ ] Implement connection, stale/offline, freshness, and authentication state.
- [ ] Render opportunities, applications, relationships, outreach, and recent
  operations from the real projection store.
- [ ] Keep operation and correlation IDs visible and copyable.
- [ ] Clear only plugin cache; never mutate vault files or server data.
- [ ] Run plugin test and build commands from Task 5.
- [ ] Commit: `feat: add Ultradex operator monitor view`.

### Task 7: Add governed mutation workflows

**Files:**

- Create: `integrations/obsidian-ultradex/src/mutations/command-controller.ts`
- Create: `integrations/obsidian-ultradex/src/mutations/command-forms.ts`
- Create: `integrations/obsidian-ultradex/src/mutations/operation-tracker.ts`
- Modify: `integrations/obsidian-ultradex/src/views/monitor-view.ts`
- Modify: `integrations/obsidian-ultradex/src/components/contract-state.ts`
- Modify: `integrations/obsidian-ultradex/styles.css`
- Create: `integrations/obsidian-ultradex/tests/command-controller.test.ts`
- Create: `integrations/obsidian-ultradex/tests/operation-tracker.test.ts`

- [ ] Write failing tests proving one UI submission causes one SDK submission,
  operation polling cannot resubmit, and a refusal remains a refusal.
- [ ] Render explicit forms for the nine canonical command methods.
- [ ] Show the idempotency key and consequence summary before confirmation.
- [ ] Require a second explicit confirmation for `outreach.send`.
- [ ] Track accepted handles through bounded operation/event polling.
- [ ] Preserve refused, failed, and unverifiable outcomes with server reason,
  operation ID, correlation ID, and events.
- [ ] Resolve and render the exact approval contract and terminal execution
  receipt. Label receipts `server-recorded`; do not claim local signature
  verification while no trusted public-key registry exists.
- [ ] Disable mutations when authentication, freshness, or connectivity is
  ambiguous.
- [ ] Run plugin test and build commands from Task 5.
- [ ] Commit: `feat: add governed mutations to Obsidian operator`.

### Task 8: Prove the isolated local operator loop

**Files:**

- Create: `tests/integration/test_obsidian_operator_runtime.py`
- Create: `scripts/create-obsidian-test-vault.sh`
- Create: `docs/obsidian-operator.md`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] Write an integration test for one synthetic `opportunities.create`
  mutation across API, JetStream, worker, projection, event, and signed receipt.
- [ ] Prove the scoped command credential cannot administer delegations.
- [ ] Add a script that creates or updates one explicit test-vault plugin
  directory without touching a working vault.
- [ ] Build the plugin and install it into the separate test vault.
- [ ] Load Obsidian, open the operator view, refresh, submit the synthetic
  mutation, and capture only non-private evidence.
- [ ] Document setup, SecretStorage enrollment, commands, failure semantics,
  local runtime, and the production rollout gate.
- [ ] Run fresh full verification:
  - `python -m pytest -q`
  - `python -m compileall -q api core sdk ultradex_sdk tests migrations`
  - `python -m build`
  - `python -m pip check`
  - `npm test --workspaces`
  - `npm run build --workspaces`
  - `git diff --check`
- [ ] Commit: `test: prove isolated Obsidian operator loop`.

### Task 9: Canonical review and handoff

- [ ] Push each stacked branch to Forgejo.
- [ ] Open one Forgejo PR per reviewable unit; target the correct parent branch
  for stacked PRs.
- [ ] Run Forgejo Actions and Snotra advisory review.
- [ ] Resolve findings with fresh verification.
- [ ] Record exact branch, commit, PR, CI, test-vault, and runtime evidence.
- [ ] Do not merge.
- [ ] Present the explicit remaining gates: per-PR merge approval, secrets,
  deployment, working-vault installation, and production mutation approval.
