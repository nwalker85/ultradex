# CCC Phase 0 — Mimir Tenancy Implementation Map and Bounded Briefs

- **Status:** Draft (Supervisor implementation map; briefs are ready to dispatch once Nate says go on each)
- **Date:** 2026-09-03
- **Owner:** Nate Walker
- **Program:** Linear initiative *Career Command Center Rebuild* → project *CCC Rebuild — Phase 0: Mimir Tenancy* (RAV-1630, RAV-1631, RAV-1632, RAV-1633; RAV-1657 ADR-0001 acceptance; RAV-1659 codename; RAV-1671 ADR-0002 ratification) and *Phase 1: Data Model* (RAV-1672 DDL, RAV-1673 mapping, RAV-1674 binding + resolver client)
- **Contracts this map implements:** ADR-0001 §2/§2.2 (Accepted 2026-09-03), **ADR-0002 scope containment** (`docs/decisions/0002-ccc-scope-containment-model.md`, Proposed) which conforms to **ADR-0006 Identity Fabric Scope Hierarchy** (Outline <https://outline.ravenhelm.dev/doc/wbhKcUoeKs>), the Mimir Tenant Scope and CCC Identity Resolution Design (`nwalker85/mimir-schema` branch `docs/ccc-tenancy-resolver-design`), ADR-022, and the galdr reference authz (`nate/audio-app` `main` @ `a251c87`, `lib/authz/*`, `authz/*.cedar`, `authz/*.fga`).

## 0. Verified current state (live repo reads, 2026-09-03)

| Seam | File (mimir-ts `origin/main` @ `82cd089`) | Finding |
|---|---|---|
| Base entity | `packages/schema/src/base.ts` `BaseEntitySchema` / `createEntitySchema` | No tenancy or scope field. `additionalProperties`-style strictness comes from zod object defaults (strips unknown keys). |
| Person | `packages/schema/src/entities/person.ts` | `tenantId: z.string().optional()` is the **only** tenant field in the repo (`git grep tenantId` → one hit). Raw `email`, `phone`, `officePhone`, `phones[]`, `accounts[]`, `rigUserId`, `voiceId` live on the same shape. `PersonTypeEnum` already has `contact`. |
| Entity types | `packages/schema/src/enums/index.ts` `EntityTypeEnum` | `person` exists; **no `organization` type** (matches the tenant-scope design's "MIS v1 has neither"). |
| Identity grammar | `packages/schema/src/identity.ts` | `classify()` accepts any `type:slug(:slug)+`; an opaque `organization:company:<uuidv7>` is "conformant" only if the uuid passes `GENERIC_ID_RE` (lowercase hex + dashes: yes). |
| Storage / reads | `packages/core/src/entity.ts` `EntityService.get/list/create/update` | `get` = `db.select('entity', id)`; `list` builds `WHERE type/lifecycleState` only. **No caller context reaches the query layer.** |
| Graph | `packages/core/src/query.ts` `QueryEngine.traverse/blastRadius/explain/summary` | Raw SurrealDB `->edge->entity.*` traversals; no filtering. |
| API | `apps/api/src/app.ts` | `cors({ origin: '*' })`; OpenAPI text says "Currently unauthenticated". No middleware chain for principal. `/health` at root. |
| Entity routes | `apps/api/src/routes/entities.ts` | list/get/create/update/retire/merge/delete; get → `404 ENTITY_NOT_FOUND` when null (the 404 shape to reuse for deny). |
| Portal (only tenant-aware code) | `apps/api/src/routes/portal.ts` + `routes/tenant.ts` | Route `/t/{tenant}/api/mimir/v1/portal/{workspace}` filters **in memory** by `entity.tenant`/`attributes.tenant` string claims — a path-derived tenant, i.e. exactly what ADR-0006/ADR-0002 forbid. |
| Canonical URL | `packages/core/src/url/canonical.ts` `parseCanonicalPath` | Requires `/t/{tenant}/{interface}`. |
| Conformance | `conformance.yaml:33` | `path_policy: "/t/{tenant}/api/rest/v{version}/{resource}/{id}/commands/{command}"`. |
| Ingress | `nate/traefik-config` `hrafngud/dynamic/ravenhelm.yml:78` | `mimir-api` router → `mimir-api-norns` (`10.10.25.100-102:30084`), **no `oauth2-proxy-auth` middleware** (galdr, puter, jarvis routers have it). |
| Deploy | `deploy/norns-values/mimir-api.yaml`, `deploy/base/network-policy.yaml` | Helm values for norns; NetworkPolicy default-deny ingress + intra-namespace. |
| Versions | `packages/schema/package.json` `0.1.0`; OpenAPI `0.3.0` | MIS v2 + path-shape change ⇒ MAJOR per ADR-0006 and the tenant-scope design. |

Live security finding (unchanged since the handoff): `GET https://mimir-api.ravenhelm.dev/api/v1/entities` needs no credential. Until RAV-1630 ships, live Mimir is an untrusted read.

## 1. Build order and dependencies

```text
RAV-1631 schema (MIS v2: tenantId + scope, organization type, person contact shape)
   └─ RAV-1632 scoped resolution (core + api + graph + graphql + mcp), needs the schema fields
        └─ RAV-1630 gate (principal → OpenFGA ∧ Cedar) can land in parallel with 1632 but must be wired
           in front of 1632's scope context; neither is "done" alone
             └─ RAV-1633 Brynn test = conformance fixture (in-repo) + deployed proof (runtime-verifier)
```

Lanes: each brief is one worktree in the conformant unit
`/Users/nate/src/hrafngud.ravenmask.net/nate/mimir-ts/` (`.bare` + siblings), branch
`<type>/rav-<n>-<slug>`, one PR per brief, Sonnet worker, Fable review. The
Supervisor creates the worktree before dispatch. Traefik change is a separate
PR in `nate/traefik-config` (exact-artifact deploy rail).

Migration of existing data is **not** in these briefs (tenant-scope design
"Migration and rollback" steps 1–2, 4–6 are a separate gated workstream; see §6).

## 2. Brief RAV-1631 — base-level `tenantId` + `scope` on MISEntity (MIS v2)

**Write scope:** `packages/schema/**`, `packages/core/src/entity.ts` (validation only), `seeds/**`, `packages/schema` version + CHANGELOG, generated SDK/MCP surfaces that derive from the schema (`packages/sdk`, `apps/mcp`, `apps/api/openapi.json` regeneration).

**Do:**
1. `base.ts`: add to `BaseEntitySchema`
   - `tenantId: z.string().regex(/^[a-z][a-z0-9-]{1,62}$/)` (required);
   - `scope: ScopeSchema` (required) per ADR-0002 §2: closed object with `ring` enum, ring-conditional coordinate fields, derived `key`; `.superRefine` enforcing invariants 1–2 (`tenantId === 'estate'` ⇔ `ring === 'installation'`, else `tenantId === scope.tenant`; no coordinates outside the ring);
   - export `scopeKey(scope)` (pure) producing the canonical key grammar (ADR-0002 §2) and `scopeContains(outerKey, innerKey)` (prefix test on `/`-delimited segments, not raw string prefix, so `o/rav` does not contain `o/ravenhelm`).
2. `enums/index.ts`: add `'organization'` to `EntityTypeEnum`; add `ScopeRingEnum`; add relationship types `AFFILIATED_WITH` (person→organization) and `CONTACT_OF` (person→organization, cross-scope declared) if absent; mark which relationship types are cross-scope-declared (a `CROSS_SCOPE_RELATIONSHIPS` set).
3. `entities/organization.ts` (new): `createEntitySchema({ type: 'organization', qualifierField: 'organizationType', shape: { organizationType: enum(company|nonprofit|government|school|association|other), legalName?, displayName, verifiedDomains[] , aliasNames[], resolutionState: active|disputed|retired } })`; refine `tenantId === 'estate'` (organizations are installation-scoped by ADR-0001 §2 / ADR-0002 §4). Register in `entities/index.ts`, SDL emit, seed models.
4. `entities/person.ts`: **remove** `tenantId` from the shape (folded into base). Add `resolutionState`, `organizationRefs[]` (FK → organization, `AFFILIATED_WITH`), `roleLabels[]`. Refine: when `personType === 'contact'` the raw fields `email`, `phone`, `officePhone`, `phones`, `accounts`, `rigUserId`, `voiceId` **must be absent** (tenant-scope design field disposition table); keep them for `employee|contractor|family` (Rig platform persons) unchanged in this brief.
5. `identity.ts`: add `organizationId()`/`personContactId()` helpers producing `organization:company:<uuidv7>` / `person:contact:<uuidv7>` (uuidv7 via `crypto.randomUUID` is v4 — use a small v7 generator; state which). Ensure `classify()` treats them as conformant.
6. `packages/core/src/entity.ts` `create()/update()`: validation now fails without `tenantId`+`scope`; `update()` must **refuse** any change to `tenantId`/`scope` (ADR-0002 invariant 5) with a typed `EntityValidationError('scope is immutable; use reconciliation')`. Store `scope.key` top-level in the SurrealDB record and define an index on it (`DEFINE INDEX entity_scope_key ON entity FIELDS scopeKey`) in the schema bootstrap.
7. `seeds/infrastructure/*.yaml`: every seed gets `tenantId: estate`, `scope: {ring: installation, installation: ravenhelm}`.
8. Versioning: `@mimir/schema` MAJOR bump (breaking base shape), OpenAPI `info.version` MAJOR, `conformance.yaml` schema version note; CHANGELOG entry citing ADR-0001 §2.2, ADR-0002, and Outline `wbhKcUoeKs`.

**Acceptance (tests in-repo, `pnpm test` green):** `base.test.ts` — entity without `tenantId`/`scope` fails; `estate` with non-installation ring fails; tenant ring with `tenantId ≠ scope.tenant` fails; `scopeKey` golden strings for every ring; `scopeContains` true/false table incl. the `o/rav` vs `o/ravenhelm` case. `person` contact with `email` fails; employee with `email` passes. `organization` with `tenantId ≠ estate` fails. `EntityService.update` changing scope throws. Seeds load. OpenAPI snapshot test updated intentionally (diff reviewed).

## 3. Brief RAV-1632 — scope-filtered resolution in `@mimir/core` and `apps/api` (cross-scope read → 404)

**Write scope:** `packages/core/src/{entity,query,client,index}.ts`, `apps/api/src/{app,schemas}.ts`, `apps/api/src/routes/{entities,graph,portal,tenant,reconcile,snapshots,aiops,backstage}.ts`, `apps/api/src/graphql/*`, `apps/mcp/**` (pass-through only), `packages/core/src/url/canonical.ts`, `conformance.yaml`.

**Do:**
1. Introduce `ScopeContext` in `@mimir/core`: `{ principalRef, visibleScopeKeys: string[] /* grants */, installationKey }`. Every `EntityService` read (`get`, `list`, `count*`) and every `QueryEngine` method takes it as the **first** parameter; there is no default and no overload without it (a missing context is a compile error, not an empty result).
2. Filter at the query, not in memory: `WHERE (scopeKey = $k OR string::starts_with(scopeKey, $k + '/')) …` OR-joined over `visibleScopeKeys`, plus the installation key (estate entities are visible to every authorized caller). `get()` returns `null` when the record exists but is out of scope — the route already maps `null` → 404 `ENTITY_NOT_FOUND`; the body must be byte-identical to the absent case.
3. Graph: `traverse/blastRadius/explain` post-filter every returned node **and** edge to visible scope keys, and never include an out-of-scope node even as an edge endpoint id (ADR-0002 §6 traversal row; Linear RAV-1632 "traversal must not leak"). Relationship create refuses non-containment endpoints unless the type is in `CROSS_SCOPE_RELATIONSHIPS` (409 with a closed refusal body, or 404 if either endpoint is invisible — check visibility first).
4. Routes: mount the OpenAPI routers under `/t/{org}/p/{project}/api/mimir/v1/…` (ADR-0002 §5). The path `{org}`/`{project}` is parsed into a *claimed* scope key; the request is refused with 404 **before lookup** unless the claimed key is contained in one of the principal's grants (RAV-1630 supplies the grants). Keep `/api/health` unscoped. Delete the in-memory `entityBelongsToTenant` path filtering in `portal.ts`/`tenant.ts`; portal projections use the same `ScopeContext`. Rename `{tenant}`→`{org}` + add `/p/{project}` in `canonical.ts` and `conformance.yaml` `path_policy`. Add the closed binding-resolver read `GET …/api/mimir/v1/bindings/{workspace_id}` returning the tenant-scope design response shape extended by ADR-0002 §4 (registry storage = a `binding` SurrealDB table; the *admin write command* is out of this brief — seed via a scripted governed command with receipt in RAV-1633's fixture only).
5. GraphQL resolvers and MCP tools call the same services with the request's `ScopeContext`; MCP receives a **workload** principal (RAV-1630) — no anonymous path remains.

**Acceptance:** unit tests with an in-memory/embedded SurrealDB: same `get` returns the org-scoped person for context A (grant on `i/ravenhelm/t/ravenhelm/o/ravenhelm`) and `null` for context B (grant on `…/o/other`), and for context C (grant on `i/ravenhelm/t/other-tenant`); estate `organization` resolves for A, B, C; `traverse` from the estate organization yields the person edge only for A; a `/t/other/p/x/…` path with A's grants → 404 before any DB call (assert the DB mock was not invoked); relationship create person(A-org)→person(B-org) refused. OpenAPI snapshot updated; `pnpm lint/test/build` green.

## 4. Brief RAV-1630 — the AND-gate in front of `mimir-api` (oauth2-proxy → principal → OpenFGA ∧ Cedar, fail closed)

**Write scope:** `apps/api/src/authz/**` (new, ported from galdr), `apps/api/src/app.ts` (middleware only), `apps/api/server.ts` or equivalent custom HTTPS entry for mTLS peer identity, `authz/mimir.cedar`, `authz/mimir.fga`, `authz/model-hash.txt`, `deploy/norns-values/mimir-api.yaml` (env + SPIRE mounts), `scripts/verify-devops.sh` additions, `conformance.yaml`. Separate PR: `nate/traefik-config` `hrafngud/dynamic/ravenhelm.yml` `mimir-api` router + `mimir-api-signin` router.

**Port map (galdr → mimir-ts):**

| galdr file (`lib/authz/`) | Port as | Change |
|---|---|---|
| `types.ts` | `authz/types.ts` | Resources become `{type:'scope', key}` and `{type:'entity', id, scopeKey}`; actions `view | write | admin | resolve`; `GraphFacts.scopeKey` replaces `tenantId`; `ServicePrincipal.service` enum = `ccc-domain-service | mimir-mcp` (SPIFFE-attested workloads) |
| `principal.ts` | `authz/principal.ts` | Verbatim rules: trust `X-Auth-Request-User`/`-Email` only on the Traefik mTLS peer; reject Zitadel `sub` UUIDs; trusted email domains → local-part uid; dev mode only with `AUTHZ_ENGINE_MODE=dev` |
| `mtls.ts`, `mtls-material.ts` | `authz/mtls.ts` | Same SPIFFE-URI-SAN-only peer resolution; peers `traefik`, `ccc-domain-service`, `mimir-mcp` |
| `openfga-client.ts` | `authz/openfga-client.ts` | Store/model ids from env; **the store is Forseti's** (Forseti = sole OpenFGA); the model in `authz/mimir.fga` is ADR-0002 §3 verbatim; `model-hash.txt` + startup check refuse to boot on drift |
| `graph.ts` | `authz/graph.ts` | `graphOnScope(principal, scopeKey, action)` / `graphOnEntity(principal, entityId, scopeKey, action)` → Check on `scope:<key>` / `entity:<id>`; `listVisibleScopeKeys(principal)` → ListObjects(`scope`, `can_view`) which becomes `ScopeContext.visibleScopeKeys` for RAV-1632. Tuple sync on startup writes `scope#parent` chains from the binding registry + config-declared admin grants (`AUTHZ_ADMIN_UIDS`, default `nate` → `admin` on `scope:i/ravenhelm`) |
| `cedar.ts` | `authz/cedar.ts` | WASM evaluator unchanged; `authz/mimir.cedar` = galdr's policies with `recognize`→`resolve` for workloads and `upload`→`write` |
| `authorize.ts` | `authz/authorize.ts` | Unchanged shape; service principals constrained to `resolve` on the installation scope |
| `http.ts` | `authz/hono.ts` | Hono middleware `requireScope(action)` sets `c.set('scopeContext', …)`; every deny → the exact 404 body from `routes/entities.ts` |
| `startup-check.ts` | `authz/startup-check.ts` | Fail boot if OpenFGA unreachable, model hash mismatch, or Cedar file unparsable (production mode) |

**Do (app):** remove `cors({origin:'*'})` (allowlist the UI origins); mount the middleware before every router except `/api/health`; wire `ScopeContext` from `listVisibleScopeKeys`; MCP app gets the workload principal path. **Do (ingress):** in `ravenhelm.yml` add `middlewares: [oauth2-proxy-auth]` to `mimir-api` (priority 100, `HeaderRegexp(Cookie, _oauth2_proxy=)`) and a `mimir-api-signin` router (priority 50 → `oauth2-proxy-local`) mirroring `jarvis-authed/jarvis-signin`; ship via the file's exact-artifact rail with Nate's typed confirmation. Note the NetworkPolicy already denies non-namespace ingress; the NodePort `30084` from hrafngud Traefik is the only path in, and the mTLS peer gate makes header spoofing on the LAN moot.

**Acceptance:** `authz/authorize.test.ts` + `adr022.test.ts` ports (drift test reads the `.cedar` text); unauthenticated → 404; Traefik-peer + valid uid → allowed on granted scope; Zitadel-UUID user header → 404; OpenFGA down → 404; Cedar deny → 404; `AUTHZ_HALTED=1` → 404 for everything. `bash scripts/verify-devops.sh` green. Live: after the rail runs, `curl -s -o /dev/null -w '%{http_code}' https://mimir-api.ravenhelm.dev/api/v1/entities` from the Mac returns `302` (signin) and the same with a valid `_oauth2_proxy` cookie for `nate` returns `200` for an estate entity — captured as the RAV-1630 receipt.

## 5. Brief RAV-1633 — the Brynn test (fixture + deployed proof)

**Write scope:** `apps/api/src/authz/brynn.test.ts`, `scripts/verify-brynn.sh`, `seeds/fixtures/brynn.yaml` (fixture-only seed, never applied to production by CI), Linear evidence.

**Fixture** (ADR-0002 §6 table, every row): seed via governed commands with receipts a binding for workspace `ccc-fixture`, `organization:company:<uuidv7>` "JAGGAER" @ `i/ravenhelm`, `person:contact:<uuidv7>` "Brynn Ireland" @ `i/ravenhelm/t/ravenhelm/o/ravenhelm`, tuples: `user:nate admin scope:i/ravenhelm/t/ravenhelm/o/ravenhelm`, `user:outsider viewer scope:i/ravenhelm/t/ravenhelm/o/other`, `user:foreign admin scope:i/ravenhelm/t/other`. Assert the seven rows (200/200/404/404/404/no-leak/fail-closed) and that the two 404 bodies are byte-identical to the absent-entity 404.

**Deployed proof (runtime-verifier, not the implementer):** `scripts/verify-brynn.sh` runs the same seven rows against `https://mimir-api.ravenhelm.dev` using oauth2-proxy sessions for `nate` and a second Zitadel test principal, **from the Mac** (hrafngud→norns NodePort probing is not representative), captures status codes + body hashes, and posts the receipt on RAV-1633. Both must pass before Phase 1 resolution work touches live Mimir.

## 6. Out of these briefs (separate gated work, tracked before Phase 1 "org/contact resolve under tenant policy")

- Data migration of existing SurrealDB entities to MIS v2 (inventory + scratch restore + backfill `estate` + person quarantine) — tenant-scope design steps 1–6, 8; needs its own RAV and a backup/restore receipt first.
- The binding-registry **admin command** with receipt/audit (tenant-scope design §"Workspace-to-tenant mapping"), and the closed identity **resolver** endpoint (`…/resolve`) — Phase 1, **RAV-1674**, after RAV-1633.
- Frigg-owned scope administration; Mimir only proves scope existence.
- `mimir-ui` (legacy/admin) under the new namespace — Loki is the target projection framework per `AGENTS.md`.

## 7. Custody note

The Mimir tenant-scope design cited by ADR-0001 lives on the **GitHub-only**
`nwalker85/mimir-schema` checkout (`/Users/nate/src/github.com/nwalker85/mimir-schema`,
branch `docs/ccc-tenancy-resolver-design`, no `origin` remote). Forgejo has no
`mimir-schema` repository under any owner (verified 2026-09-03 with the `nate`
PAT), so that repo is not migrated and GitHub is its primary; the custody guard
nevertheless blocks reads there because the repo is private. Either migrate
`mimir-schema` to Forgejo (`nate/mimir-schema`) or add it to the GitHub-primary
allowlist before RAV-1631 is dispatched, so the worker can read the design under
custody rules.
