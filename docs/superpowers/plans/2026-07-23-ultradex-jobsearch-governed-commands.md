# Ultradex Governed Job-Search Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Deliver JS-U03: the canonical job-search command API, official Python SDK
methods, NATS JetStream task contracts, bounded executors, durable lifecycle events,
signed execution receipts, and exact approval enforcement for outreach.

**Architecture:** Legacy contact commands remain on their existing ARQ compatibility
path. Job-search mutations use a separate `JobSearchGatewayService` that derives actor
identity server-side, validates `JobSearchCommandV1`, atomically records accepted
intent, and publishes the canonical command to JetStream. A separate worker validates
the same task contract, dispatches through a closed executor registry, atomically
writes projections/events/receipts, and publishes the terminal lifecycle event. Ports
for source ingestion, scoring, Dex resolution, and sending fail closed until JS-U04
or JS-U06 supplies a concrete adapter.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, `nats-py`,
`cryptography` Ed25519, `ravenhelm-contracts==0.2.0`, pytest.

## Frozen scope

- Base SHA: `17e02b9e46cd9400347d249db8fea8d70455a3ba`.
- Branch: `feat/jobsearch-governed-commands`.
- Worktree: `/Users/nate/var/worktrees/ultradex-jobsearch-commands`.
- Official client boundary: `sdk.UltradexClient`.
- Command catalog: the nine names in
  `ravenhelm_contracts.jobsearch_v1.COMMAND_NAMES_V1`.
- No authenticated LinkedIn scraping, Gmail mining, YC parsing, Dex network calls,
  model scoring, or outbound message delivery belongs in this unit.
- No migration of the deployed contact-analysis ARQ path belongs in this unit.
- No raw message, mailbox, LinkedIn, Dex note, prompt, completion, resume, or job
  description content may enter commands, logs, events, receipts, or projections.
- A command is not complete without a terminal operation state, canonical lifecycle
  event, and structurally valid Ed25519-signed `ExecutionReceiptV1`.
- Outreach send is refused unless the approval is unexpired and binds the exact
  outreach ID, message commitment, and channel.

## Configuration contract

Add these 1Password-backed environment variables to `.env.example` and Compose:

- `NATS_URL`
- `ULTRADEX_ACCOUNTABILITY_HMAC_KEY` — base64url, at least 32 decoded bytes.
- `ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY` — base64url, exactly 32 decoded bytes.
- `ULTRADEX_RECEIPT_KEY_ID` — an independently registered `pairwise:v1:` key ID.
- `ULTRADEX_EXECUTOR_PAIRWISE_ID` — the worker's `pairwise:v1:` identity.
- `ULTRADEX_SERVICE_VERSION`, `ULTRADEX_DEPLOYMENT_SHA`, and
  `ULTRADEX_ENVIRONMENT`.

No secret receives a source-code default. Test fixtures inject deterministic test
keys; production code refuses receipt issuance when configuration is absent or
malformed.

---

### Task 1: Persist accepted commands, approval evidence, events, and receipts

**Files:**

- Modify: `core/models.py`
- Modify: `core/jobsearch_models.py`
- Modify: `core/__init__.py`
- Create: `migrations/versions/20260723_0002_jobsearch_commands.py`
- Modify: `tests/test_jobsearch_migrations.py`
- Create: `tests/test_jobsearch_command_models.py`

- [x] Write failing migration and model tests for:
  `jobsearch_commands`, `jobsearch_evidence_refs`, `jobsearch_approvals`,
  `jobsearch_lifecycle_events`, and `jobsearch_execution_receipts`.
- [x] Assert the revision depends on `20260723_0001`, upgrades from base to head,
  downgrades cleanly, and leaves no JS-U03 tables behind.
- [x] Add `OperationStatus.REFUSED` without changing legacy status spellings.
- [x] Add exact SQLAlchemy rows:
  - accepted command: operation/command IDs, command name, actor, delegation,
    idempotency key, canonical context, validated parameters, timestamps;
  - evidence reference: the seven fields of `JobSearchEvidenceReferenceV1`;
  - approval: approval ID, outreach ID, commitment, channel, approver, issued,
    expiry, status;
  - lifecycle event: event/operation IDs, event type, canonical event payload,
    publication timestamp;
  - receipt: receipt/operation/event IDs, status, reason code, canonical receipt
    payload, receipt hash, timestamps.
- [x] Add unique constraints for one accepted command and one terminal receipt per
  operation, plus indexes used by operation, outreach, and unpublished-event reads.
- [x] Export only the public row types needed by repositories and tests.
- [x] Run:
  `python -m pytest tests/test_jobsearch_migrations.py tests/test_jobsearch_command_models.py -q`.
- [x] Commit: `feat: persist governed job-search command records`.

### Task 2: Issue and validate privacy-preserving execution receipts

**Files:**

- Create: `core/jobsearch_receipts.py`
- Create: `tests/test_jobsearch_receipts.py`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Modify: `.env.example`

- [x] Write failing tests that construct succeeded, failed, and refused receipts and
  validate them with `ExecutionReceiptV1.from_dict`.
- [x] Assert successful receipts contain a result commitment and no reason code;
  failed/refused receipts use only the V1 reason catalog.
- [x] Assert tenant, actor, action, idempotency, and result values are represented by
  keyed HMAC commitments or opaque/pairwise identifiers, never copied into a public
  receipt field.
- [x] Assert tampering breaks Ed25519 signature verification against the configured
  public key.
- [x] Implement base64url parsing, opaque ID generation, pairwise ID derivation,
  domain-separated HMAC commitments, whole-minute timestamps, receipt construction,
  signing via `execution_receipt_signing_bytes_v1`, structural validation, hashing,
  and signature verification.
- [x] Add `cryptography` to runtime dependencies.
- [x] Run: `python -m pytest tests/test_jobsearch_receipts.py -q`.
- [x] Commit: `feat: issue signed job-search execution receipts`.

### Task 3: Build the canonical gateway and JetStream task boundary

**Files:**

- Create: `core/jobsearch_commands.py`
- Create: `core/jobsearch_nats.py`
- Modify: `core/operation_service.py`
- Modify: `core/idempotency_service.py`
- Modify: `core/__init__.py`
- Create: `tests/test_jobsearch_command_gateway.py`
- Create: `tests/test_jobsearch_nats.py`
- Modify: `requirements.txt`

- [x] Write failing tests proving the Gateway:
  - constructs and re-validates `JobSearchCommandV1`;
  - derives actor identity and ignores caller-supplied actor data;
  - preserves the complete `CorrelationContextV1`;
  - binds idempotency to actor, delegation, command, and parameters;
  - publishes once on an exact replay and conflicts on a changed envelope;
  - uses `ultradex.jobsearch.commands.v1.<command-slug>`;
  - passes the idempotency key as `Nats-Msg-Id`;
  - never publishes an unregistered command;
  - returns a failed handle and durable failed receipt after a post-acceptance
    publish failure.
- [x] Add a `JobSearchTaskPublisher` protocol and a JetStream implementation. Stream
  setup is idempotent and covers command and lifecycle subjects.
- [x] Add a closed command-to-subject registry derived from
  `COMMAND_NAMES_V1`; do not concatenate arbitrary caller input into a subject.
- [x] Add a `JobSearchGatewayService` that validates first, then atomically persists
  operation, idempotency binding, accepted command, and accepted lifecycle event,
  and only then publishes.
- [x] Extend operation mutations with `commit=False` support so a terminal state,
  event, projection write, and receipt can share one transaction.
- [x] Add `nats-py` to runtime dependencies.
- [x] Run:
  `python -m pytest tests/test_jobsearch_command_gateway.py tests/test_jobsearch_nats.py tests/test_idempotency_atomicity.py tests/test_command_acceptance.py -q`.
- [x] Commit: `feat: add canonical JetStream job-search gateway`.

### Task 4: Execute the command catalog with refusal, retry, and approval safety

**Files:**

- Create: `core/jobsearch_executors.py`
- Create: `core/jobsearch_worker.py`
- Modify: `core/jobsearch_projections.py`
- Modify: `core/event_producer.py`
- Modify: `core/__init__.py`
- Create: `tests/test_jobsearch_executors.py`
- Create: `tests/test_jobsearch_worker.py`

- [x] Write failing executor tests for every canonical command name.
- [x] Implement closed protocols for source ingestion, opportunity scoring, Dex
  relationship resolution, and outreach delivery. Default bindings raise structured
  domain refusals rather than making network calls.
- [x] Implement local handlers:
  - `opportunities.create` loads a validated evidence reference and creates a
    discovered opportunity;
  - `applications.transition` appends immutable stage history for an existing
    application;
  - `outreach.prepare` creates a pending-approval row containing only the message
    commitment;
  - `outreach.approve` creates a 24-hour approval contract and marks the exact
    outreach approved;
  - `evidence.export` returns only an opaque accountability export reference.
- [x] Implement port-backed handlers:
  `sources.ingest`, `opportunities.score`, `relationships.sync`, and
  `outreach.send`.
- [x] Assert default port bindings refuse with a terminal event and receipt.
- [x] Assert outreach send refuses missing, expired, cancelled, wrong-outreach,
  wrong-channel, and wrong-commitment approvals without calling the sender.
- [x] Assert a valid approval calls the sender once and stores only the returned
  evidence reference.
- [x] Add retryable execution errors: attempts below the configured limit emit a
  bounded retry event and do not mint a terminal receipt; the final attempt fails
  with exactly one receipt. A replay after a terminal receipt returns the stored
  outcome and performs no second mutation.
- [x] Stamp projection rows/checkpoints from the terminal event identity. Event,
  projection, operation state, approval, and receipt commit atomically.
- [x] Implement a pull consumer with explicit ACK after terminal persistence,
  delayed NAK for retryable failures, and TERM for malformed/unregistered tasks.
- [x] Run:
  `python -m pytest tests/test_jobsearch_executors.py tests/test_jobsearch_worker.py -q`.
- [x] Commit: `feat: execute governed job-search command catalog`.

### Task 5: Expose the REST command API and official Python SDK

**Files:**

- Create: `api/routes/v2/jobsearch_commands.py`
- Modify: `api/dependencies.py`
- Modify: `api/main.py`
- Modify: `sdk/ultradex_sdk.py`
- Modify: `ultradex_sdk/__init__.py`
- Create: `tests/test_jobsearch_command_api.py`
- Modify: `tests/test_sdk.py`
- Modify: `tests/test_auth_boundary.py`

- [x] Write failing API tests for authenticated submission of all nine command names,
  exact shared `ContractHandleV1` OpenAPI projection, required idempotency keys,
  validation failures, authority refusal, replay, conflict, and unavailable NATS.
- [x] Expose:
  `POST /api/v2/job-search/commands/{command_name}` with a parameters-only JSON
  object. Actor identity comes exclusively from the bearer principal.
- [x] Keep authentication/authorization HTTP errors outside operation truth. Return
  governed accepted, refused, or failed handles for accepted command intent.
- [x] Add `UltradexClient.submit_jobsearch_command` plus one typed convenience method
  per canonical command. The SDK sends REST only; it never imports NATS or database
  code.
- [x] Re-validate outbound parameters locally with the shared contract by creating a
  client-side canonical envelope whose server-owned context is not sent.
- [x] Assert the SDK preserves idempotency, delegation, and correlation headers and
  never sends `X-Actor-Id`.
- [x] Run:
  `python -m pytest tests/test_jobsearch_command_api.py tests/test_sdk.py tests/test_auth_boundary.py -q`.
- [x] Commit: `feat: expose official job-search command SDK`.

### Task 6: Wire the runnable NATS worker without cutting over legacy ARQ

**Files:**

- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `Dockerfile`
- Modify: `api/main.py`
- Create: `tests/test_jobsearch_runtime.py`

- [x] Write failing runtime tests proving the API uses a JetStream publisher when
  configured, reports a governed failure when it is not bound, and closes its NATS
  connection on shutdown.
- [x] Add a JetStream-enabled NATS service and a separate `jobsearch-worker` service
  to Compose. Preserve the existing Redis and ARQ worker unchanged.
- [x] Document secret custody, NATS subjects, API/SDK examples, worker command,
  refusal behavior for unbound adapters, and the explicit non-delivery guarantee.
- [x] Document that JS-U04 and JS-U06 must replace the default refusal ports before
  source ingestion or outbound delivery can be claimed live.
- [x] Run:
  `python -m pytest tests/test_jobsearch_runtime.py tests/test_runtime_baseline.py tests/test_worker_contract.py -q`.
- [x] Commit: `docs: wire governed job-search command runtime`.

### Task 7: Full verification and review

**Files:**

- Modify only files required to fix verified findings.

- [x] Install the changed dependency set into the isolated worktree environment.
- [x] Run the complete suite:
  `python -m pytest -q`.
- [x] Run:
  `python -m compileall -q api core sdk ultradex_sdk tests migrations`.
- [x] Run: `python -m build`.
- [x] Create a clean temporary virtual environment, install the wheel, and run:
  `python -m pip check`.
- [x] Verify the packaged SDK imports and validates all nine command methods without
  importing service-only modules.
- [x] Inspect:
  `git diff --check`,
  `git status --short`,
  `git log --oneline origin/main..HEAD`,
  and `git diff --stat origin/main...HEAD`.
- [x] Review authority, idempotency, retry, receipt, approval, raw-content,
  cardinality, migration, SDK-only, and legacy-compatibility boundaries.
- [x] Update the execution manifest with JS-U03 PR evidence and the honest JS-U04
  dependency state.
- [x] Push `feat/jobsearch-governed-commands` and open a GitHub PR against `main`.
  Do not merge without explicit approval for that PR.

## Acceptance proof

- All nine shared command contracts are reachable only through the authenticated
  command API and official SDK.
- Every accepted task has one durable accepted command row and at most one terminal
  signed receipt.
- Every terminal outcome has a canonical job-search lifecycle event and a valid
  `ExecutionReceiptV1`.
- Exact idempotent retries do not republish or repeat a terminal mutation.
- Retryable failures do not claim terminality before the attempt budget is exhausted.
- Outreach cannot send without exact, live approval evidence.
- Unbound source/scoring/Dex/sender ports refuse safely and perform no external I/O.
- Legacy contact commands remain green on ARQ.
- Projections contain only normalized facts, commitments, and opaque evidence
  references.
- Code complete, PR open, merged, deployed, and live remain separately reported
  states.
