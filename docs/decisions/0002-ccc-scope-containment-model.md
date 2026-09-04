# ADR-0002: Scope Containment Model for Mimir Tenancy and the CCC Data Model

- **Status:** Proposed (amends ADR-0001 §2 and §2.2; not authorized for implementation until operator ratification)
- **Owner:** Nate Walker
- **Date:** 2026-09-03
- **Linear:** RAV-1671 (ratification decision); implements into RAV-1631, RAV-1632, RAV-1674
- **Amends:** ADR-0001 *Career Command Center Rebuild — Storage Tiers, Tenancy, and Phasing* (Accepted 2026-09-03; `docs/decisions/0001-ccc-rebuild-tiers-tenancy-phasing.md`, ultradex PR #41)
- **Conforms to:**
  - **ADR-0006: Identity Fabric Scope Hierarchy & Containment Model** — Outline
    <https://outline.ravenhelm.dev/doc/wbhKcUoeKs> (published 2026-09-03; bridges
    ADR-022 and the Platform Architecture Control Surface). Source ADR: Vitki
    `docs/architecture/decisions/0006-fabric-native-urls-and-scope.md`
    (`/Users/nate/src/hrafngud.ravenmask.net/nate/vitki/main/…`, Accepted 2026-09-03).
  - ADR-022 Security Specification (Outline `iDxbMKTpPf`); Platform Architecture
    Control Surface (Outline `6w3phcyyQN`); ADR-008 Storage Tiers (Outline `ttqmgmey5u`).
  - Career CRM Relational Schema Design (`docs/superpowers/specs/2026-08-31-career-crm-relational-schema-design.md`, amended 2026-09-01).
  - Mimir Tenant Scope and CCC Identity Resolution Design (`nwalker85/mimir-schema`,
    branch `docs/ccc-tenancy-resolver-design`,
    `docs/superpowers/specs/2026-09-01-tenant-scope-ccc-identity-resolution-design.md`, Review).
  - CCC GTM Wire Contract Design (`nate/ravenhelm-contracts`, branch `docs/ccc-gtm-contract-design`, Review).

## Context (BECAUSE)

ADR-0001 and the Mimir tenant-scope design express tenancy as one flat,
required `tenantId` on `MISEntity`, with the reserved value `estate` for
estate-global entities, and address services as `canonical host + /t/{tenant}`.

On 2026-09-03 the estate published **ADR-0006** (Outline `wbhKcUoeKs`), which is
now the canonical containment model for every product and tenant, CCC included.
It defines **scope** as concentric rings:

```text
installation                outermost deploy scope (environment lives here)
  └─ tenant                 customer / contract / default IdP / halt
       └─ organization      brand or shared-services bench
            ├─ org.domain* / org.project* / org.group*     (span applications)
            └─ application: <app>
                 ├─ app.domain* / app.project* / app.group*  (inherit org; may override)
                 └─ resource
```

and fixes three things a flat `tenantId` cannot express:

1. **Document/resource home scope is `app.project`**, and visibility is an
   assignment `(principal | access_group) + role + scope` — never a per-record
   share flag.
2. **The URL namespace is `/t/{org}/p/{project}/app/{app_name}`**, where `{org}`
   is the *organization* slug and `{project}` the *app.project* slug. The `/t/`
   segment is kept for continuity but carries the organization, and the path is
   an addressing claim, never a grant.
3. **Org-level constructs are inherited by app-level constructs**; people sets
   (`org.group`) are org constructs, not app or document containers.

Three concrete conflicts therefore exist between the accepted ADR-0001 and the
canonical model, and this ADR resolves them before Phase 0 implementation
starts:

| # | ADR-0001 / tenant-scope design says | ADR-0006 says | Resolution here |
|---|---|---|---|
| C1 | canonical host + `/t/{tenant}` | `/t/{org}/p/{project}/app/{app}`; `{org}` = organization | §5: adopt the ADR-0006 namespace for Mimir and CCC; tenant is resolved by containment, never from the path |
| C2 | `MISEntity.tenantId` (flat; `estate` reserved) | home scope is a ring with coordinates | §2: keep `tenantId` as the required fast filter **and** add a closed `scope` record; `estate` ≡ the installation ring |
| C3 | CCC `workspace_id` ↔ Mimir tenant, 1:1 | a product workspace is an `app.project` under an organization under a tenant | §4: workspace ↔ `app.project` (`application = ccc`); the Mimir-owned binding registry returns the full scope, not only the tenant |

## Decision

### 1. Vocabulary

- Use **scope** for every ring. There is no type named "band" and no
  product-local "tenant" that is not the ADR-0006 tenant ring.
- Mimir's reserved `tenantId = estate` **is** the ADR-0006 `installation` ring
  for the Ravenhelm estate installation. Estate-global entities (a `Host`, an
  `organization:company:<uuidv7>`) are installation-scoped; nothing else lives
  there.
- Scope slugs use the tenant-scope design grammar `^[a-z][a-z0-9-]{1,62}$`.

### 2. MIS v2 base scope contract (amends ADR-0001 §2.2 and the tenant-scope design §"MIS v2 base entity contract")

Every MIS v2 entity carries **both**:

```text
tenantId          required string   'estate' | <tenant slug>          (unchanged: the fast tenant filter)
scope             required record   (closed; additionalProperties: false)
  ring            installation | tenant | organization
                  | org.domain | org.project | org.group
                  | app.domain | app.project | app.group
  installation    required slug                                       (e.g. ravenhelm)
  tenant          required slug for every ring except installation
  organization    required slug for organization and every inner ring
  application     required slug for app.domain / app.project / app.group
  domain          required slug for org.domain / app.domain
  project         required slug for org.project / app.project
  group           required slug for org.group / app.group
  key             derived canonical scope key (below); stored, indexed, never authored by a client
```

Invariants (schema `refine`, enforced at every write and at migration):

1. `tenantId = 'estate'` ⇔ `scope.ring = 'installation'`; otherwise `tenantId = scope.tenant`.
2. Coordinates outside the ring are absent (an `organization`-ring entity has no `application`).
3. `scope.key` is derived, unique per scope, and is the OpenFGA object id.
4. A relationship between two entities whose scope keys are not in a containment
   line (one a prefix of the other) is refused unless the relationship type is
   declared cross-scope **and** both endpoint policies authorize it
   (tenant-scope design base constraint 2 generalised to rings).
5. Scope never changes by ordinary update. Re-homing is a governed
   reconciliation command that preserves the prior scope as provenance.

**Canonical scope key** (containment is a prefix test; this is what OpenFGA,
SurrealDB indexes, and the Postgres projections store):

```text
installation   i/{installation}
tenant         i/{installation}/t/{tenant}
organization   i/{installation}/t/{tenant}/o/{organization}
org.domain     …/o/{organization}/d/{domain}
org.project    …/o/{organization}/p/{project}
org.group      …/o/{organization}/g/{group}
application    …/o/{organization}/a/{application}
app.domain     …/a/{application}/d/{domain}
app.project    …/a/{application}/p/{project}
app.group      …/a/{application}/g/{group}
```

Example: a CCC contact homed at the operator organisation has
`scope.key = i/ravenhelm/t/ravenhelm/o/ravenhelm`; the CCC workspace is
`i/ravenhelm/t/ravenhelm/o/ravenhelm/a/ccc/p/<workspace>`.

### 3. Visibility and the AND-gate (amends ADR-0001 §2 third bullet; conforms to ADR-022)

- **Visibility = `entity#can_view`** derived from the entity's home scope:
  a principal (or access group) with `viewer` or stronger on scope **G** can see
  every entity whose `scope.key` has **G's key as a prefix** (G equal or outer).
  A grant on an inner scope never reaches an outer resource.
- OpenFGA model (Forseti is the sole OpenFGA authority; Mimir loads its model into
  Forseti's store and pins `OPENFGA_MODEL_ID`):

```text
model
  schema 1.1
type user
type group
  relations
    define member: [user]
type workload
type scope
  relations
    define parent: [scope]
    define admin: [user, group#member] or admin from parent
    define uploader: [user, group#member] or admin or uploader from parent
    define viewer: [user, group#member] or uploader or viewer from parent
    define can_view: viewer
    define can_upload: uploader
    define can_admin: admin
    define resolve: [workload]
type entity
  relations
    define home: [scope]
    define can_view: can_view from home
    define can_upload: can_upload from home
    define can_admin: can_admin from home
```

  `scope#parent` tuples form the ring chain (`app.project → application →
  organization → tenant → installation`). `org.group` membership is `group#member`;
  the ADR-0006 pattern "`org.group` + viewer @ `app.project`" is the tuple
  `group:<key>#member viewer scope:<app.project key>`.
- **Cedar** receives only graph facts plus context (halted, locked, policy
  version), exactly as galdr does (`nate/audio-app` `authz/audio-app.cedar`).
  Either engine deny, error, or unavailability ⇒ deny. **Deny = 404, never 403.**
- Effective scope for a request = agreement of: authenticated principal
  (rig `uid`, never Zitadel `sub`), the Mimir-owned workspace→scope binding, the
  entity's `scope.key` parentage, and the Forseti Check. Any disagreement,
  including a path that names a different `{org}` or `{project}`, fails **before
  lookup** with a 404.

### 4. CCC scope mapping (amends ADR-0001 §2 second bullet and relational spec §1–§2)

| CCC concept | Scope | Notes |
|---|---|---|
| Ravenhelm estate | `installation = ravenhelm` | `tenantId = estate` |
| CCC operator tenant | `tenant = ravenhelm` | ADR-0001 ruling, unchanged |
| CCC operator organisation | `organization = <org>` | **operator decision** (default proposal: `ravenhelm`) |
| CCC application | `application = ccc` | fixed; the codename (RAV-1659) names repos, not the application scope slug |
| CCC workspace (`workspaces.id`) | `app.project = <workspace slug>` under `a/ccc` | one workspace ↔ one app.project; the ADR-0006 "document home" |
| `organizations` projection target | `organization:company:<uuidv7>` @ installation (`estate`) | "JAGGAER exists" is an estate fact |
| `contacts` projection target | `person:contact:<uuidv7>` @ **organization** ring (default) or `app.project` when workspace-private | tenant-private by containment; visible to every app in the org that holds a grant, which is the ADR-0006 people-are-org-constructs rule |

**Binding registry (Mimir-owned; supersedes "workspace-to-tenant" wherever it
appears).** The registry record and the resolver response gain the ring
coordinates; the field names `tenant_mapping_version`, `tenant_registry_revision`
and `tenant_mapping_lineage_ref` used by the GTM wire contract are **kept** for
wire stability and now version the whole binding:

```text
workspace_id
tenant_id                  scope.tenant
organization_id            scope.organization
application_id             'ccc'
project_id                 scope.project        (app.project slug)
scope_key                  derived canonical key
mapping_version, registry_revision, effective_at, retired_at, authority_ref, lineage_ref
```

**CCC Postgres (relational spec §1):** `workspace_tenant_binding_projection`
becomes `workspace_scope_binding_projection` with the same lifecycle rules and
the added `organization_id`, `application_id`, `project_id`, `scope_key`
columns. `organizations` and `contacts` projections add `mimir_scope_key text NULL`
(present exactly when `resolution_status = resolved`) so an audit can show the
ring a resolution was made in. Nothing else in the relational spec changes.

**Admin boundary (ADR-0006 §4).** Frigg/kvasir owns tenants, organisations,
domains, projects, groups, roles and assignments. Mimir's binding command
(tenant-scope design §"Workspace-to-tenant mapping") must **prove the target
scope exists** and never creates a ring as a side effect. Until Frigg is live,
the seed binding for the CCC workspace is written by that same governed Mimir
administrative command with operator approval and a receipt; chat, a route, a
config value, or a CCC row cannot create it.

### 5. URL namespace (resolves C1; amends ADR-0001 §2 fourth bullet and the tenant-scope design §"Namespace contract")

```text
/                                              → 302 → /t/{defaultOrg}/p/{defaultProject}/app/{app}
/t/{org}/p/{project}/app/ccc                   CCC operator seat (Phase 3)
/t/{org}/p/{project}/api/ccc/v2/…              CCC command/query API (Phase 2)
/t/{org}/p/{project}/api/mimir/v1/entities/…   Mimir entity reads/writes, scope-filtered
/t/{org}/p/{project}/api/mimir/v1/graph/…      traversal / blast-radius / explain, scope-filtered
/t/{org}/p/{project}/api/mimir/v1/resolve      the closed identity resolver (tenant-scope design)
/t/{org}/p/{project}/api/mimir/v1/bindings/…   workspace→scope binding resolver (read) and admin command
/api/health                                     liveness (no org)
```

- `{org}` is the organisation slug; `{project}` is the app.project slug. **The
  tenant is not in the path**; it is the parent of `{org}` in the registry.
- Vanity hosts (`mimir-api.ravenhelm.dev`, `ccc.ravenhelm.dev`) are aliases only.
- The path is a claim. Mismatch between path scope, principal grants, binding, and
  entity parentage ⇒ 404 before lookup.
- Installation-scoped (estate) entities are readable through any org/project path
  the caller is authorized for; the path selects the caller's context, not the
  entity's home.
- Per ADR-0006, authz tuple or path-shape changes are **MAJOR** while experimental.

Consequences inside `mimir-ts` (main @ `82cd089`): the portal route
`/t/{tenant}/api/mimir/v1/portal/{workspace}` (`apps/api/src/routes/portal.ts`),
`conformance.yaml` `path_policy: /t/{tenant}/api/rest/…`, and
`packages/core/src/url/canonical.ts` (`parseCanonicalPath` requires `/t/{tenant}`)
all rename `{tenant}` → `{org}` and insert `/p/{project}`.

### 6. The Brynn test, restated under scopes (amends ADR-0001 §2 acceptance)

Given `person:contact:<uuidv7>` with `displayName = Brynn Ireland`,
`tenantId = ravenhelm`, `scope = {ring: organization, installation: ravenhelm,
tenant: ravenhelm, organization: <org>}`, and `organization:company:<uuidv7>`
(JAGGAER) at `estate`:

| Caller | Path | Expected |
|---|---|---|
| `nate` with `admin` on `scope:i/ravenhelm/t/ravenhelm/o/<org>` | `/t/<org>/p/<ws>/api/mimir/v1/entities/person:contact:<id>` | 200, entity |
| `nate` | same path, `…/entities/organization:company:<jaggaer>` | 200 (estate entity) |
| principal with grants only on another organisation or tenant | either path to the person | 404, body indistinguishable from absent |
| unauthenticated / missing Traefik mTLS peer | any | 404 |
| `nate` | `/t/<other-org>/p/<ws>/…/person:contact:<id>` (path tamper) | 404 before lookup |
| foreign principal | `…/graph/traverse/organization:company:<jaggaer>` | 200 with **no** person edge surfaced |
| OpenFGA or Cedar unreachable | any | 404 (fail closed) |

Both the `mimir-ts` conformance fixture and the deployed-runtime check
(RAV-1633) assert every row.

## Deltas to apply on ratification (the amendment list)

| Artifact | Change |
|---|---|
| ADR-0001 §1 table, §2, §2.2, Phasing row 0 | replace "tenant-scoped/`/t/{tenant}`/workspace↔tenant" wording with references to this ADR §2–§5; add ADR-0006 (`wbhKcUoeKs`) to *Depends on* |
| Relational schema spec §1, §2 | rename `workspace_tenant_binding_projection` → `workspace_scope_binding_projection` + columns; add `mimir_scope_key` to `organizations`/`contacts`; cite `wbhKcUoeKs` |
| Mimir tenant-scope design (mimir-schema) | add §2 `scope` record + key grammar; generalise base constraint 2; rewrite "Namespace contract" to §5; binding registry + resolver fields per §4; cite `wbhKcUoeKs` |
| CCC GTM wire contract (`control-surface/v2` correlation context) | add `organization_id`, `project_id`, `scope_key` next to `tenant_id`/`workspace_id` (schema still in Review, so no version bump beyond v2) |
| `mimir-ts` | `conformance.yaml` path policy; `canonical.ts`; `portal.ts` route; OpenFGA model + Cedar policy files (§3) |
| Linear RAV-1631 / RAV-1632 | description points at this ADR §2–§3 as the contract |

## Consequences

- One containment model across Vitki, Galdr, CCC and Mimir; CCC inherits Frigg's
  assignments instead of inventing a share model.
- A CCC contact is usable by every application in the operator's organisation
  that holds a grant, without cross-tenant leakage: the ADR-0001 privacy ruling
  holds because organisation ⊂ tenant.
- Mimir's scope filter is a prefix test on one indexed string; the tenant filter
  is unchanged for the common case.
- Path-shape and tuple changes are MAJOR; `@mimir/schema` moves to MIS v2 with
  this ADR folded in, not as a second breaking release later.
- Frigg remains out of scope; Mimir's binding command is the interim, governed
  way to seed the CCC scope and is itself recorded.

## Non-goals

Implementing Frigg; host authentication (LDAP/Dogtag/JumpCloud); migrating
Galdr's or Vitki's existing tuples; choosing the CCC codename (RAV-1659);
authorizing any production migration, deploy or cutover.

## Open decisions for the operator

1. **Default home ring for CCC contacts:** `organization` (recommended, §4) vs
   `tenant` (ADR-0001 literal) vs `app.project` (workspace-private).
2. **The CCC operator organisation slug** under tenant `ravenhelm` (proposal:
   `ravenhelm`; the ADR-0006 household example uses `household` for family
   scope, which is *not* the career workspace).
3. Confirm keeping the `/t/` path letter with organisation semantics (ADR-0006
   already rules this; listed only so the rename in `mimir-ts` is explicitly
   approved as MAJOR).
