# ADR-0001: Career Command Center Rebuild — Storage Tiers, Tenancy, and Phasing

- **Status:** Proposed (draft; not authorized for implementation until operator ratification)
- **Owner:** Nate Walker
- **Date:** 2026-09-01
- **Supersedes:** the `ultradex` runtime as the CCC system of record (on cutover, per §7 gates)
- **Depends on / conforms to:** Platform Architecture Control Surface (Outline `6w3phcyyQN`); ADR-022 Security Specification, Accepted (`iDxbMKTpPf`); ADR-008 Storage Tiers & the Mimir Catalog as Sidr (`ttqmgmey5u`); Career CRM Relational Schema Design (`docs/superpowers/specs/2026-08-31-career-crm-relational-schema-design.md`); Project Factory + repo-lifecycle gates.

## Context (BECAUSE)

The current Career Command Center runs on `ultradex`: a disjointed accretion —
a pm2/k0s split, an unmigrated-then-repaired database, a wiped-and-refilled
store, ad-hoc auth, and a UI that never became the daily surface. It works, but
it is not built to the estate's now-accepted doctrine. This ADR defines the
**rebuild** as a doctrine-conformant career CRM, and the order in which it is
built.

Operator rulings (2026-09-01) this ADR records:
1. **Mimir must conform to the security and control-surface doctrine — tenancy
   at minimum.** A person entity (e.g. Brynn Ireland) scoped to a tenant is
   surfaced only to callers in that tenant. This makes Mimir tenancy **phase 0**,
   a prerequisite, not a parallel track.
2. **CCC is built as fresh Project-Factory scaffolds; `ultradex` is frozen** as
   legacy behind an explicit current→target mapping. No rebuild-in-place.
3. Build order is **data model → API/integration → UI**, on top of phase 0.

## Decision

### 1. Storage tiers (ADR-008), applied to CCC

CCC is a three-tier system joined on the Mimir `entity_id`:

| Tier | Owns for CCC | Examples |
|---|---|---|
| **Mimir** | Identity + relationships: the *nouns*. Organizations and contacts resolve to Mimir entities (tenant-scoped — see §2). | `organization:jaggaer`, `person:brynn-ireland` (tenant `ravenhelm`) |
| **Postgres** | Mutable transactional current-state with a lifecycle: the pursuit funnel. This is the relational schema spec. | `leads`, `opportunities`, `pipeline_stages`, `submissions`, `employment_offers`, `contract_agreements`, `opportunity_qualification`, `next_best_action` |
| **ClickHouse** | Append-only observation/history at volume (only if/when volume warrants; at single-operator scale these may remain append-only Postgres tables). | interaction history, score snapshots, source-record versions |

The relational schema's canonical `organizations` and `contacts` become
**workspace-local projections** carrying `entity_id uuid NULL` +
`resolution_status`, resolving to tenant-scoped Mimir nodes. The pursuit
lifecycle stays authoritative in Postgres. "Latest value"/churny fields
(advocacy score, last-contacted, fit score) never promote to a Mimir node.
History sinks are downstream of the transactional owner via outbox/CDC; the log
never decides "current". CCC's databases and tables register in the Mimir
catalog (Database/Table/Stream entities) via the introspection registrar on
deploy.

### 2. Tenancy model (the phase-0 core)

- **Tenancy is a base-level property**, not per-entity-type. `MISEntity` gains a
  required `tenantId`; `person.tenantId` (today optional, ad hoc) folds into it.
  Entities may be **estate-global** (a `Host`) or **tenant-scoped** (a CCC
  `person`); the base field expresses which.
- **Organizations resolve to estate-global Mimir entities** ("JAGGAER exists" is
  a global identity fact). **Contacts are tenant-scoped `person` entities**
  ("Brynn is my contact" is tenant-private). CCC's `workspace_id` maps to the
  Mimir tenant.
- **`mimir-api` is placed behind the AND-gate:** oauth2-proxy forwardAuth →
  header→principal (reject Zitadel `sub` UUID; trusted-domain email local-part →
  uid) → OpenFGA (relationship) ∧ Cedar (context), fail closed. Copy galdr
  (`nate/audio-app` `lib/authz/*`); do not reinvent. Query resolution filters by
  the caller's tenant; **cross-tenant read → 404, never 403.**
- Namespace convention (repo-lifecycle gate): canonical host + `/t/{tenant}`
  path; vanity domains are aliases only.

**Phase-0 acceptance (the Brynn test):** a `person` entity scoped to tenant
`ravenhelm` resolves — and surfaces as a CCC contact — only for a caller in that
tenant, and returns 404 to every other caller. Today `mimir-api` is
unauthenticated (`cors *`, no forwardAuth) and un-tenanted; that is the gap this
phase closes, and until it closes live Mimir is treated as an untrusted read.

### 3. Control-surface conformance (all CCC services)

Named commands (202 + ContractHandle; acceptance ≠ completion); reads via a
side-effect-free query API exposing freshness + lineage; append-only events on
NATS JetStream; the full audit evidence chain per state change; `accountability.v1`
proof-package profile; **SDK-only clients** (`@ravenhelm/sdk-ts`; no raw APIs /
NATS in the browser). Conformance is executable against `ravenhelm-contracts`
fixtures + CI (Project-Factory `repo-baselines` generates the declarations and
gates). Agent/tool-facing responses: absence in-band, one response shape, closed
schemas, no examples.

### 4. Repos (Project Factory)

Fresh scaffolds, `ultradex` frozen:

| Repo | Lane | Role |
|---|---|---|
| CCC domain service | `fastapi-service` | Command/query/gateway + executors + projectors for the pursuit funnel; owns the Postgres tier and the Mimir resolution client |
| CCC UI | `next-web` | Operator seat on the gullveig model (`@ravenhelm/sdk-ts` + `@ravenhelm/ui-react`) |
| Mimir tenancy | *(changes in existing `mimir-schema` / `mimir-ts`)* | Phase 0 — no new repo; base-level `tenantId`, tenant-scoped resolution, the auth gate |

Codename is an operator decision (Norse lab tier) and is recorded at intake
before scaffolding. Each repo carries an authoritative `AGENTS.md`,
`package-surface.json` (7 keys), SemVer policy, CHANGELOG, and the observability
route (Prometheus/Grafana/Vidar/Mimir/Thor) documented.

## Phasing

| Phase | Deliverable | Exit criterion |
|---|---|---|
| **0 — Mimir conformance** | Auth gate on `mimir-api`; base-level `tenantId`; tenant-scoped resolution | the Brynn test passes against deployed Mimir |
| **1 — Data model** | Postgres pursuit-lifecycle schema (from the spec) + Mimir org/contact resolution + Sidr contracts + current→target mapping | schema migrates cleanly; a lead→opportunity round-trips; org/contact resolve to tenant-scoped entities |
| **2 — API / integration** | Command/query/gateway + JetStream + receipts + Forseti PDP + Dex/Gmail governed provenance | a governed command round-trips end-to-end with a proof package; conformance CI green |
| **3 — UI** | CCC operator seat on the gullveig model | the daily surface renders funnel + next-best-action through the SDK, deny=404, freshness first-class |

## Cutover (ADR-011 discipline — this is a cutover, not a deploy)

Swapping the CCC system of record from `ultradex` to the new stack is a
**cutover**. It requires, as separate ratified artifacts before execution: the
**current→target mapping** (every current table/column → target or explicit
retirement; org/company reconciliation; backfill + referential-integrity
ordering; validation queries + acceptance thresholds); a **data-migration plan**;
and **loud decommission** of the `ultradex` runtime. No phase merges to
production, and no legacy table is deleted, without its explicit approval gate.

## Non-goals

UI navigation/labels; exact stage names/probabilities; ORM/Alembic code;
authorizing the production migration or legacy decommission (that is §7 + operator
ratification); changing the command/receipt/SDK/custody architecture the control
surface already defines.

## Consequences

- Mimir becomes multi-tenant and gated — an estate-wide improvement CCC pays for
  but everything benefits from.
- CCC's contact-privacy tension resolves cleanly: contacts *can* be Mimir person
  entities because Mimir is now tenant-aware.
- `ultradex` stays running until the cutover gates pass; the two stacks are
  explicitly separate until then.
- The data-loss class that wiped CCC on 2026-08-29 is designed out: durable
  entity IDs independent of Dex/LinkedIn, immutable provenance, restrictive
  deletion at integration boundaries, and (operationally) a backed-up store.

## Open decisions for the operator

1. **Codename** for the CCC rebuild (Norse lab tier) — blocks repo scaffolding.
2. Whether ClickHouse enters at phase 1 or is deferred until interaction/score
   volume warrants it (default: defer; keep append-only in Postgres).
3. The org/company reconciliation rules for the current→target mapping (phase 1).
