# Job Search Intelligence Platform Execution Manifest

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each child plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a private SDK-first job-search intelligence platform with governed commands, read-only projections, safe source adapters, and correlated observability and audit evidence.

**Architecture:** Shared wire contracts are implemented first, followed by language instrumentation libraries and then Ultradex domain behavior. Each repository changes through an isolated branch and PR; cross-repository consumers use released contracts or conformance fixtures rather than copying undocumented shapes.

**Tech Stack:** JSON Schema 2020-12, TypeScript, Python 3.11+, Go 1.21+, FastAPI, Strawberry GraphQL, SQLAlchemy, NATS JetStream, OpenTelemetry, Prometheus, Loki, Tempo, Langfuse, Grafana.

## Global Constraints

- The official SDK is the sole supported client boundary.
- REST accepts commands; GraphQL serves side-effect-free queries; internal execution uses task contracts.
- Every mutation returns a `ContractHandle`; refusal is a structured result.
- Telemetry is a redacted projection and cannot replace immutable events or receipts.
- The job-search domain is private and operator-only; restricted content is referenced, not copied.
- Prometheus labels use only bounded dimensions; governance identifiers are forbidden as label values.
- Every work unit uses a dedicated worktree, test-first changes, conventional commits, and a PR.

---

## Dependency graph

```text
JS-C01 control-surface/job-search contracts
  +-> JS-O01 Python instrumentation context
  +-> JS-G01 Go instrumentation context
  +-> JS-U01 Ultradex baseline and Python SDK
        +-> JS-U02 persistence and projections
        +-> JS-U03 commands and executors
        +-> JS-U04 source adapters
        +-> JS-U05 Go SDK and CLI
        +-> JS-U06 MCP and automation
        +-> JS-U07 telemetry projector and operator artifacts
        +-> JS-U08 computed registers and conformance
```

## Bounded work units

| ID | Repository | Deliverable | Depends on | Review gate |
|---|---|---|---|---|
| JS-C01 | `ravenhelm-contracts` | Versioned control-surface and job-search schemas, bindings, fixtures | none | TypeScript/Python/schema parity |
| JS-O01 | `ravenhelm-observability-py` | Canonical context, propagation, redaction, metric-label guards | JS-C01 shapes | Shared golden/adversarial fixtures |
| JS-G01 | new `ravenhelm-observability-go` | Go context, propagation, safe logs, metric-label guards | JS-C01 shapes | Go fixture parity and repo lifecycle conformance |
| JS-U01 | `ultradex` | Green baseline, official Python SDK, `ContractHandle`, GraphQL operation reads | JS-C01 | Python red-green suite and legacy compatibility |
| JS-U02 | `ultradex` | Opportunity/application/relationship/outreach persistence and read projections | JS-U01 | migration and query tests |
| JS-U03 | `ultradex` | Commands, Gateway contracts, NATS tasks, receipts, approval-gated outreach | JS-U02 | idempotency, refusal, retry, receipt tests |
| JS-U04 | `ultradex` | Gmail, LinkedIn-safe, Dex, manual/web adapter ports and executors | JS-U03 | custody/redaction and fixture tests |
| JS-U05 | `ultradex` | Go SDK and thin CLI with deterministic JSON and exit codes | JS-U01, JS-G01 | Go unit/contract tests; no raw API in commands |
| JS-U06 | `ultradex` | MCP, agent skill, and n8n bridge using Python SDK only | JS-U01, JS-U03 | raw-client static guard and integration tests |
| JS-U07 | `ultradex` plus fleet config | Event-to-telemetry projector, dashboard, alerts, catalog, runbooks | JS-O01, JS-U03 | redaction, cardinality, lag, receipt coverage |
| JS-U08 | `ultradex` plus dossier projection | Computed Blind Spots/Broken Bindings and end-to-end canary | JS-U07 | outage invariants and accountability export |

## Execution status (2026-07-23)

| ID | State | Evidence / blocker |
|---|---|---|
| JS-C01 | PR 18 open; green | `ravenhelm-contracts` contract PR is open with required checks green. |
| JS-O01 | PR 6 open; green | Python instrumentation PR is open with required checks green. |
| JS-G01 | pending | New-repository lifecycle work has not started. |
| JS-U01 | PR 2 open; reviewed | Independent review is clear; authentication, executable worker registry, atomic scoped idempotency, governed 503 handles, SDK delegation, bounded GraphQL reads, honest nullable freshness, shared OpenAPI/runtime validation, compile, build, and compatibility wheel checks pass. |
| JS-U02 | PR 3 open; reviewed | [Ultradex PR 3](https://github.com/nwalker85/ultradex/pull/3) is stacked on PR 2. Versioned migrations, contract-backed persistence reads, and a read-only GraphQL projection surface are implemented. Final-review fixes preserve same-connection in-memory startup, canonical checkpoint keys, validated outreach item provenance, and exact `RelationshipV1` schema scope. Verification passes with 103 tests and one pre-existing strict MCP XFAIL; the focused JS-U02 suite passes all 60 tests. Compile, wheel/sdist build, dependency, and diff checks pass. Independent whole-unit review reports no Critical, Important, or Minor findings. Do not merge before PR 2 and the required merged/published `ravenhelm-contracts==0.2.0` artifact. |
| JS-U03–JS-U08 | pending | Dependency boundaries remain frozen below; no implementation has started in these units. |

## Orchestration rules

- Freeze exact repository, base SHA, allowed paths, interfaces, test command, and expected failure before assigning a worker.
- Do not ask a bounded worker to choose architecture, create a repository, change a cross-repo contract, or merge its own PR.
- A dependent unit may begin against a reviewed branch but cannot claim release compatibility until the dependency PR is merged and published.
- A functional unit is incomplete without lifecycle events, receipt semantics, redacted telemetry, and triplet/function coverage.
- Preserve separate proof for code merged, package published, deployed, and live behavior.
