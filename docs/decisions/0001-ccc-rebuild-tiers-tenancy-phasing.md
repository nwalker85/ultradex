# ADR-0001: Career Command Center Rebuild — Storage Tiers, Tenancy, and Phasing

- **Status:** Accepted (2026-09-03; ratified by Nate Walker)
- **Owner:** Nate Walker
- **Date:** 2026-09-01
- **Supersedes:** the CCC runtime and client authorities selected by ADR-014 and
  its amendments, but only after this exact ADR is ratified and the migration,
  rollback, cutover, and operator-approval gates below pass
- **Depends on / conforms to:** Platform Architecture Control Surface (Outline `6w3phcyyQN`); ADR-022 Security Specification, Accepted (`iDxbMKTpPf`); ADR-008 Storage Tiers & the Mimir Catalog as Sidr (`ttqmgmey5u`); Career CRM Relational Schema Design (`docs/superpowers/specs/2026-08-31-career-crm-relational-schema-design.md`); Mimir Tenant Scope and CCC Identity Resolution Design (`nwalker85/mimir-schema`, Review); CCC GTM Wire Contract Design (`nate/ravenhelm-contracts`, Review); Project Factory + repo-lifecycle gates.

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

### Relationship to accepted ADR-014

ADR-014 and its accepted amendments remain the current CCC authority until a
separately approved cutover completes. This ADR does not amend them by
being written, reviewed, committed, merged, scaffolded, or deployed in shadow
mode.

This Accepted ADR is the decision record for a planned
replacement and explicitly supersedes these ADR-014 selections only at the
approved cutover instant:

| ADR-014 authority before cutover | Target authority after cutover | Migration rule |
|---|---|---|
| Dex is the CCC contact system of record. | Mimir is canonical organization/person identity; CCC Postgres owns workspace-local identity projections and pursuit state. | Dex remains a source adapter and temporary source-content custodian during migration. It cannot remain an identity writer or competing contact authority after acceptance. |
| Ultradex is the Python career middleware and CCC domain runtime. | A fresh Project-Factory CCC domain service owns commands, queries, executors, projectors, and Postgres pursuit state. | Ultradex continues serving the legacy stack until writers are fenced and the target round-trip passes. It is then loudly decommissioned, not left dual-writing. |
| The local Svelte glass uses `@ultradex/sdk`; React is prohibited for that accepted surface. | A fresh `next-web` operator surface uses generated `@ravenhelm/sdk-ts` and `@ravenhelm/ui-react`. | The Svelte glass remains the legacy UI until cutover. The target UI does not reuse `@ultradex/sdk`, and no browser receives a raw service client. |

The following ADR-014 boundaries are preserved rather than superseded: CCC is
the AAL career vertical; Týr never dispatches work; ML stays in backend Python
services rather than the browser; Obsidian remains frozen; and Hyperdex is not
a production CCC system of record. The temporary vakr/k0s Hyperdex experiment
does not become a migration source or target merely because this rebuild is
approved.

Ratification must publish the accepted decision to the canonical CCC
documentation surface and leave an explicit supersession pointer on ADR-014.
Until both the decision and later cutover are approved, implementation and
operators must follow ADR-014's Dex/Ultradex/Svelte authorities.

## Decision

### 1. Storage tiers (ADR-008), applied to CCC

CCC is a three-tier system joined on the Mimir `entity_id`:

| Tier | Owns for CCC | Examples |
|---|---|---|
| **Mimir** | Identity + relationships: the *nouns*. Organizations and contacts resolve to Mimir entities under the tenancy contract below. | `organization:company:<uuidv7>` (estate-global), `person:contact:<uuidv7>` (tenant-private) |
| **Postgres** | Mutable transactional current-state with a lifecycle: the pursuit funnel. This is the relational schema spec. | `leads`, `opportunities`, `pipeline_stages`, `submissions`, `employment_offers`, `contract_agreements`, `opportunity_qualification`, `next_best_action` |
| **ClickHouse** | Append-only observation/history at volume (only if/when volume warrants; at single-operator scale these may remain append-only Postgres tables). | interaction history, score snapshots, source-record versions |

The relational schema's `organizations` and `contacts` become
**workspace-local projections** carrying `mimir_entity_id text NULL` +
`resolution_status`, resolving to Mimir coordinates. The pursuit
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
  Mimir tenant. Mimir owns the canonical workspace-to-tenant binding registry
  and side-effect-free resolver; CCC holds only a versioned read-only
  projection and cannot change the binding locally.
- **`mimir-api` is placed behind the AND-gate:** oauth2-proxy forwardAuth →
  header→principal (reject Zitadel `sub` UUID; trusted-domain email local-part →
  uid) → OpenFGA (relationship) ∧ Cedar (context), fail closed. Copy galdr
  (`nate/audio-app` `lib/authz/*`); do not reinvent. Query resolution filters by
  the caller's tenant; **cross-tenant read → 404, never 403.**
- Namespace convention (repo-lifecycle gate): canonical host + `/t/{tenant}`
  path; vanity domains are aliases only. The path is an addressing claim, never
  a grant. Effective tenant comes from the authenticated identities, governed
  workspace mapping, entity parentage, and Forseti Check. Any disagreement among
  those inputs fails before lookup.

**Phase-0 acceptance (the Brynn test):** a `person` entity scoped to tenant
`ravenhelm` resolves — and surfaces as a CCC contact — only for a caller in that
tenant, and returns 404 to every other caller. Today `mimir-api` is
unauthenticated (`cors *`, no forwardAuth) and un-tenanted; that is the gap this
phase closes, and until it closes live Mimir is treated as an untrusted read.

### 2.1 Identity strata and delegation

CCC preserves four identities that must not collapse:

| Stratum | CCC representation | Authority meaning |
|---|---|---|
| Operator | `rig_user_id` (`nate` initially) | Person on whose behalf the action occurs; never Zitadel `sub`. |
| Durable agent | Mimir Agent `resource_id` plus `did:web` | Named CCC supervisor principal. |
| Workload | SPIRE SPIFFE identity | Attests which deployed workload is executing; never sufficient by itself. |
| Session | short-lived `did:key` reference | Per-execution key that invokes an already bounded grant. |

Every command and identity-resolution request binds all four plus the witnessed
delegation, tenant/workspace mapping version, policy version, and deployment
revision. Authentication establishes identity; Forseti authorizes the exact
action. No raw credential, path, entity ID, session key, or workload identity
mints authority.

The durable-agent binding includes the current Mimir Agent resolution reference,
registry/resolver/policy versions, lineage, validity window, lifecycle,
descriptor digest, and package-surface reference. An Agent ID alone is not a
complete command identity, and a stale, expired, inactive, or
package-mismatched resolution fails before acceptance.

Delegation uses Varar and Vor: a bounded child cannot widen its parent, and the
grant is appended to the witness ledger before release. Expired, revoked,
unwitnessed, missing, or stale-policy delegation fails closed. A consumer
surface is a projection, never an authority source.

### 2.2 Mimir schema and resolver gate

Phase 0 is a breaking MIS schema migration, not merely an API filter. The target
Mimir design defines MIS v2 with required base-level `tenantId`, reserved
`estate` scope, estate-global organizations, tenant-private people, opaque
person/organization coordinates, a governed workspace-to-tenant mapping, and a
closed resolver result of `resolved`, `unresolved`, or `ambiguous`.

The migration inventories both MIS v1 JSON Schema and the current `mimir-ts`
person/phone/account drift. Raw email, phone, office-phone, SIP ANI, provider,
and other contact identifiers move to named custody or quarantine; they are not
silently copied into MIS v2 or CCC projections.

The resolver is a side-effect-free query. It cannot create, merge, promote, or
move an entity. Those are separate governed commands. A v1 entity without an
explicit migrated scope is unavailable to tenant-scoped CCC resolution; no
caller may default it into the current tenant.

### 3. Control-surface conformance (all CCC services)

Named commands (202 + ContractHandle; acceptance ≠ completion); reads via a
side-effect-free query API exposing freshness + lineage; append-only events on
NATS JetStream; the full audit evidence chain per state change; `accountability.v1`
proof-package profile; **SDK-only clients** (`@ravenhelm/sdk-ts`; no raw APIs /
NATS in the browser). Conformance is executable against `ravenhelm-contracts`
fixtures + CI (Project-Factory `repo-baselines` generates the declarations and
gates). Agent/tool-facing responses: absence in-band, one response shape, closed
schemas, no examples.

Every state-changing flow preserves the full evidence chain:

```text
operator intent
  -> authenticated operator + agent + workload + session
  -> witnessed bounded delegation
  -> endpoint validation
  -> Forseti authorization or structured refusal
  -> operation + contract recording
  -> task publication
  -> executor identity + deployed revision
  -> attempts + side effects
  -> immutable receipt
  -> outcome event
  -> projection + freshness
  -> SDK result
  -> accountability.v1 proof package
```

If any link can change without invalidating its commitment or proof, the surface
is non-conforming.

### 4. Operator surface contract

The CCC UI is presentation only. It uses `@ravenhelm/sdk-ts`; it receives no raw
gateway, database, Mimir, or NATS credential. It renders these states as
different facts:

```text
not_submitted
accepted
in_progress
completed
refused
pending_sync
stale_projection
```

The UI follows a `ContractHandle` to a terminal receipt and projection rather
than treating `202` as success. Structured refusal is visible. Projection
freshness and lineage are first-class. Denied and foreign-tenant entities render
as absent, never as a revealing `403`. Hidden navigation is convenience, not
enforcement; each command and query remains independently gated.

### 5. Repos (Project Factory)

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

Before scaffolding, intake records codename, owner, purpose, canonical path,
forge/repository, namespace, SDK/API, identity, runner, observability, storage,
backup, and deployment authority in the repository `AGENTS.md` and Mimir. Chat
is not a registry.

### 6. Runtime files and artifact namespace

CCC transactional authority never lives in a local file. The public-only bridge
may create an immutable, unexecuted intake proposal only under:

```text
~/var/career-command-center/intake/<workspace_id>/<bundle_id>/bundle.json
```

Directory components are operator-owned, mode `0700`, non-symlinked, and
validated against the bundle. Files are mode `0600`, written through an
exclusive temporary sibling, flushed, and atomically renamed. A different
pre-existing digest is a refusal, not an overwrite. The workspace component is
an addressing claim and must match the authenticated bundle contents before
import.

No bundle contains raw private content, credentials, an authority grant, or a
completed-state assertion. Import uses the official SDK and does not advance
until each command has a terminal receipt plus expected projection readback.
Pending bundles expire after 30 days unless explicitly extended; disposition
retains metadata-only evidence for at most 90 days. A local bundle never becomes
funnel authority.

Yager task files remain owned by Yager's separate
`~/var/yager/tasks/<task_id>/` contract. CCC does not use that task directory as
a document store, CRM, approval ledger, or cross-day workflow database.

### 7. Reliability, backup, and recovery

Durable storage is not a backup. Before CCC or Mimir becomes authoritative, each
transactional store requires:

1. a documented 3-2-1 backup contract;
2. verified off-host/offsite delivery;
3. freshness and integrity evidence;
4. a scratch-database restore drill;
5. measured recovery-point and recovery-time results; and
6. a rollback path that preserves migration and audit evidence.

Mimir identity, CCC transactional state, and any ClickHouse history have
different owners and backup policies. A green pod, healthy PV, successful dump
command, or scheduled task is not recovery proof. The runtime verifier proves
the deployed revision, migrations, health, a real record round-trip, tenant
isolation, and restore behavior from the correct network vantage.

Observability binds command/contract/task/event/trace/projection identifiers and
explains behavior. `accountability.v1` receipts prove governed action. Logs and
traces never substitute for authority or execution receipts.

## Phasing

| Phase | Deliverable | Exit criterion |
|---|---|---|
| **0 — Mimir conformance** | Auth gate on `mimir-api`; base-level `tenantId`; tenant-scoped resolution | the Brynn test passes against deployed Mimir |
| **1 — Data model** | Postgres pursuit-lifecycle schema (from the spec) + Mimir org/contact resolution + Sidr contracts + current→target mapping | schema migrates cleanly; backup and scratch restore pass; a lead→opportunity round-trips; org/contact resolve under tenant policy |
| **2 — API / integration** | Command/query/gateway + JetStream + receipts + Forseti PDP + Dex/Gmail governed provenance + control-surface/jobsearch v2 contracts | a governed command round-trips end-to-end with a proof package; identity strata remain distinct; conformance CI green |
| **3 — UI** | CCC operator seat on the gullveig model | the daily surface renders funnel + next-best-action through the SDK, deny=404, command lifecycle and freshness first-class |
| **4 — Controlled GTM vertical** | Public-only Lead intake, BANT, booking proof, conversion, and exact-draft operator review/manual send | one synthetic and one operator-reviewed public-source flow prove the KPI without private connectors, a false governed-approval receipt, or autonomous send |

## Cutover (ADR-011 discipline — this is a cutover, not a deploy)

Swapping the CCC system of record from `ultradex` to the new stack is a
**cutover**. It requires, as separate ratified artifacts before execution: the
**current→target mapping** (every current table/column → target or explicit
retirement; org/company reconciliation; backfill + referential-integrity
ordering; validation queries + acceptance thresholds); a **data-migration plan**;
and **loud decommission** of the `ultradex` runtime. No phase merges to
production, and no legacy table is deleted, without its explicit approval gate.

The cutover transfers all three ADR-014 authorities together: identity from
Dex to Mimir plus CCC projections, domain runtime from Ultradex to the fresh CCC
service, and browser client from the Svelte/`@ultradex/sdk` surface to the
Next.js/generated-SDK surface. A partial switch that leaves either runtime able
to mutate the same funnel is prohibited. The gateway has exactly one active
CCC mutation epoch. Before target authority is enabled it accepts legacy
`jobsearch/v1` writes only at the legacy runtime; at target cutover it fences
those writers and accepts target `jobsearch/v2` writes only. Legacy v1 queries
and retained history may remain available read-only during reconciliation.

There is no v2-to-v1 mutation adapter, no v1 write path into target stores, and
no dual-write window. A v1 mutation presented after target cutover returns the
structured `contract_version_retired` refusal before publication or side
effect. Rollback is a separately authorized authority-epoch reversal that
fences target writers before re-enabling the legacy runtime; it is not a
runtime fallback that enables both.

Deployment follows merge only after the exact deployment gate is approved. The
rail applies migrations before starting code that could create legacy tables,
proves the expected image and revision, checks restart count and health, and
performs a real governed round-trip. A datastore, repository, or transport swap
is the cutover above, not a routine deploy.

## Non-goals

UI navigation/labels; exact stage names/probabilities; ORM/Alembic code;
authorizing the production migration or legacy decommission (that remains the
cutover package plus operator ratification); changing the
command/receipt/SDK/custody architecture the control surface already defines.

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
- A local file, Yager ledger, ClickHouse projection, UI state, or accepted
  command cannot silently become transactional or identity authority.

## Open decisions for the operator

1. **Codename** for the CCC rebuild (Norse lab tier) — blocks repo scaffolding.
2. Whether ClickHouse enters at phase 1 or is deferred until interaction/score
   volume warrants it (default: defer; keep append-only in Postgres).
3. The org/company reconciliation rules for the current→target mapping (phase 1).
