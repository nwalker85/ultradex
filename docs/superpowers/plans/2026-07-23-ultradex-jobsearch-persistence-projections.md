# Ultradex Job-Search Persistence and Read Projections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the four `jobsearch.v1` entity projections, maintain durable source-position checkpoints, and expose contract-backed, bounded, side-effect-free GraphQL reads.

**Architecture:** Alembic owns the new job-search projection schema while existing legacy tables remain on the current transitional `create_all` path. A read-only repository converts SQLAlchemy rows through the released `ravenhelm-contracts==0.2.0` Python bindings before GraphQL can expose them. Each projection page carries an honest nullable durable checkpoint: populated checkpoints expose source event, position, projection time, lag, and state; absent checkpoints remain `null`.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0.23, Alembic 1.18.5, Strawberry GraphQL, SQLite/PostgreSQL-compatible migrations, `ravenhelm-contracts==0.2.0`, pytest.

## Global Constraints

- Repository: `nwalker85/ultradex` (public, GitHub-primary).
- Base: `feat/jobsearch-observability-foundation` at `014001b5a8c458c236b615101a270bdc56bb91d6`.
- Branch/worktree: `feat/jobsearch-persistence-projections` in `/Users/nate/var/worktrees/ultradex-jobsearch-persistence`.
- This is stacked on GitHub PR 2 and cannot merge before that dependency.
- The official SDK remains the sole supported client boundary.
- REST remains command-only; GraphQL remains side-effect-free and has no mutation root.
- This unit does not implement domain commands, NATS executors, connectors, outreach sending, CLI changes, MCP changes, or telemetry export.
- The job-search domain is private and operator-only; no Gmail body, LinkedIn message, Dex note, resume content, prompt, completion, or outreach text may be stored or returned.
- Store only normalized fields, opaque custody references, redacted summaries, hashes, commitments, bounded state, and durable source-position metadata.
- `ravenhelm-contracts==0.2.0` remains the shape validator; do not copy or loosen its dataclasses.
- Every list query is keyset-paginated, deterministic, and bounded to `1..100`.
- Missing checkpoints produce `freshness: null`; never manufacture zero lag, a source event, or `fresh` state.
- Every task follows red-green-refactor, receives an independent review gate, and ends in a conventional commit with the required co-author trailer.

---

## File Map

- `alembic.ini` — repository-local Alembic configuration without credentials.
- `migrations/env.py` — online/offline Alembic environment using `core.models.Base.metadata` and a caller-provided connection when tests supply one.
- `migrations/script.py.mako` — deterministic revision template.
- `migrations/versions/20260723_0001_jobsearch_projections.py` — first reversible migration for four projections plus checkpoints.
- `core/jobsearch_models.py` — SQLAlchemy row models only; no API or command behavior.
- `core/jobsearch_migrations.py` — programmatic `upgrade head` entry point used by service startup and tests.
- `core/jobsearch_projections.py` — read-only repository, pagination value object, row-to-contract conversion, and checkpoint lookup.
- `api/graphql/jobsearch_types.py` — Strawberry projection types and contract-to-GraphQL conversion.
- `api/graphql/schema.py` — bounded query fields wired to the repository.
- `tests/test_jobsearch_migrations.py` — schema upgrade/downgrade and startup migration proof.
- `tests/test_jobsearch_projection_repository.py` — canonical conversion, ordering, filtering, pagination, privacy, and missing-checkpoint proof.
- `tests/test_graphql_jobsearch.py` — schema and mounted-route read behavior, limits, filters, freshness, and no-mutation proof.

---

### Task 1: Add a Reversible Job-Search Projection Migration

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/20260723_0001_jobsearch_projections.py`
- Create: `core/jobsearch_models.py`
- Create: `core/jobsearch_migrations.py`
- Create: `tests/test_jobsearch_migrations.py`
- Modify: `requirements.txt`
- Modify: `core/database.py`
- Modify: `core/__init__.py`

**Interfaces:**
- Produces: `run_jobsearch_migrations(database_url: str, *, connection: Connection | None = None) -> None`.
- Produces row models: `OpportunityProjectionDB`, `ApplicationProjectionDB`, `RelationshipProjectionDB`, `OutreachProjectionDB`, `ProjectionCheckpointDB`.
- Produces constants: `JOBSEARCH_PROJECTION_TABLES: frozenset[str]` and `JOBSEARCH_PROJECTION_TYPES: frozenset[str]`.
- `Database.init()` must create legacy tables and run the job-search migration
  through one `self.engine` connection and transaction.

- [x] **Step 1: Write the failing migration tests**

  Add tests that:

  ```python
  def test_upgrade_head_creates_only_versioned_jobsearch_schema(tmp_path):
      engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
      run_jobsearch_migrations(str(engine.url))
      tables = set(inspect(engine).get_table_names())
      assert {
          "alembic_version",
          "jobsearch_opportunities",
          "jobsearch_applications",
          "jobsearch_relationships",
          "jobsearch_outreach",
          "jobsearch_projection_checkpoints",
      } <= tables

  def test_upgrade_is_idempotent_and_downgrade_removes_jobsearch_tables(tmp_path):
      engine = create_engine(f"sqlite:///{tmp_path / 'roundtrip.db'}")
      run_jobsearch_migrations(str(engine.url))
      run_jobsearch_migrations(str(engine.url))
      cfg = alembic_config(str(engine.url))
      command.downgrade(cfg, "base")
      assert not (
          set(inspect(engine).get_table_names())
          & set(JOBSEARCH_PROJECTION_TABLES)
      )

  def test_database_init_preserves_legacy_tables_and_applies_jobsearch_revision(tmp_path):
      database = Database(f"sqlite:///{tmp_path / 'startup.db'}")
      database.init()
      tables = set(inspect(database.engine).get_table_names())
      assert {"operations", "contacts"} <= tables
      assert set(JOBSEARCH_PROJECTION_TABLES) <= tables
  ```

- [x] **Step 2: Run the migration tests and verify RED**

  Run:

  ```bash
  python -m pytest tests/test_jobsearch_migrations.py -q
  ```

  Expected: collection fails because `core.jobsearch_migrations` and the projection row models do not exist.

- [x] **Step 3: Define focused SQLAlchemy projection models**

  Define the following table responsibilities in `core/jobsearch_models.py`:

  - `jobsearch_opportunities`: normalized employer/title/location/role family, state, score/explanation, JSON risk flags and evidence references, row freshness, created/updated timestamps.
  - `jobsearch_applications`: opportunity reference, state, JSON stage history and artifact references, next action/deadline, row freshness, created/updated timestamps.
  - `jobsearch_relationships`: opportunity reference, opaque Dex contact reference, derived relevance fields, row freshness, created/updated timestamps.
  - `jobsearch_outreach`: opportunity/relationship references, state, channel, message commitment, approval contract reference, sent evidence reference, row freshness, created/updated timestamps. No message body column is allowed.
  - `jobsearch_projection_checkpoints`: one row per projection type with `source_event_id`, `source_event_position`, `projected_at`, `lag_ms`, and `status`.

  Use `Base` from `core.models`, explicit string lengths, `DateTime(timezone=True)`, JSON arrays, indexes for state/opportunity filters, and no cross-table foreign keys because replayed disposable projections may arrive out of order.

- [x] **Step 4: Add the Alembic environment and revision**

  Pin `alembic==1.18.5`. Configure `migrations/env.py` with:

  ```python
  from core.models import Base
  import core.jobsearch_models  # noqa: F401

  target_metadata = Base.metadata

  def run_migrations_online() -> None:
      supplied = config.attributes.get("connection")
      if supplied is not None:
          context.configure(connection=supplied, target_metadata=target_metadata)
          with context.begin_transaction():
              context.run_migrations()
          return
      connectable = engine_from_config(
          config.get_section(config.config_ini_section, {}),
          prefix="sqlalchemy.",
          poolclass=pool.NullPool,
      )
      with connectable.connect() as connection:
          context.configure(connection=connection, target_metadata=target_metadata)
          with context.begin_transaction():
              context.run_migrations()
  ```

  The revision must create and index exactly the five job-search tables and downgrade them in reverse dependency order. It must not create, alter, drop, or stamp legacy tables.

- [x] **Step 5: Add programmatic migration startup**

  Implement:

  ```python
  def alembic_config(database_url: str) -> Config:
      config = Config(str(PROJECT_ROOT / "alembic.ini"))
      config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
      config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
      return config

  def run_jobsearch_migrations(
      database_url: str,
      *,
      connection: Connection | None = None,
  ) -> None:
      config = alembic_config(database_url)
      if connection is not None:
          config.attributes["connection"] = connection
      command.upgrade(config, "head")
  ```

  In `Database.init()`, open one `self.engine.begin()` connection, pass only
  tables whose names are not in `JOBSEARCH_PROJECTION_TABLES` to
  `Base.metadata.create_all`, and then upgrade the versioned job-search schema
  through that same connection. This preserves the legacy bootstrap path,
  supports in-memory SQLite startup, and prevents `create_all` from bypassing
  the new revision.

- [x] **Step 6: Run migration and baseline tests**

  Run:

  ```bash
  python -m pytest tests/test_jobsearch_migrations.py tests/test_runtime_baseline.py -q
  ```

  Expected: all selected tests pass.

- [x] **Step 7: Commit Task 1**

  ```bash
  git add alembic.ini migrations core/jobsearch_models.py core/jobsearch_migrations.py core/database.py core/__init__.py requirements.txt tests/test_jobsearch_migrations.py
  git commit -m "feat: add versioned job-search projection schema" \
    -m "Co-Authored-By: OpenAI Codex <codex@openai.com>"
  ```

---

### Task 2: Add a Contract-Backed Read Repository

**Files:**
- Create: `core/jobsearch_projections.py`
- Create: `tests/test_jobsearch_projection_repository.py`
- Modify: `core/__init__.py`

**Interfaces:**
- Produces: `ProjectionPage[T]` with `items: tuple[T, ...]`, `freshness: ProjectionFreshnessV1 | None`, and `next_cursor: str | None`.
- Produces: immutable `ProjectedOutreach` with `item: OutreachV1` and
  `freshness: ProjectionFreshnessV1`.
- Produces: `JobSearchProjectionRepository(session: Session)`.
- Produces detail methods `get_opportunity`, `get_application`, `get_relationship`, `get_outreach`.
- Produces list methods `list_opportunities`, `list_applications`, `list_relationships`, `list_outreach`, each accepting `first: int`, `after: str | None`, and only its documented bounded filters.
- Consumes canonical `OpportunityV1`, `ApplicationV1`, `RelationshipV1`, `OutreachV1`, and `ProjectionFreshnessV1` from `ravenhelm_contracts`.

- [x] **Step 1: Write the failing repository tests**

  Seed rows directly and prove:

  ```python
  page = JobSearchProjectionRepository(db_session).list_opportunities(
      first=2,
      after=None,
      status="qualified",
  )
  assert [item.opportunity_id for item in page.items] == [
      "opportunity-01",
      "opportunity-02",
  ]
  assert page.next_cursor == "opportunity-02"
  assert page.freshness is not None
  assert page.freshness.source_event_position == "JOBSEARCH:42"
  ```

  Also assert:

  - `first=0` and `first=101` raise `ValueError`.
  - `after` applies stable `id > cursor` keyset pagination.
  - status and opportunity filters are applied in SQL.
  - a missing projection checkpoint returns `freshness is None`.
  - corrupt evidence objects, raw-content keys, malformed commitments, invalid statuses, and overlong summaries fail canonical `from_dict` validation before a result is returned.
  - list execution is two statements at most: one page query and one checkpoint query.

- [x] **Step 2: Run the focused test and verify RED**

  Run:

  ```bash
  python -m pytest tests/test_jobsearch_projection_repository.py -q
  ```

  Expected: collection fails because `JobSearchProjectionRepository` does not exist.

- [x] **Step 3: Implement row-to-contract conversion**

  Build exact dictionaries from row columns and validate them with:

  ```python
  OpportunityV1.from_dict(payload)
  ApplicationV1.from_dict(payload)
  RelationshipV1.from_dict(payload)
  OutreachV1.from_dict(payload)
  ProjectionFreshnessV1.from_dict(payload)
  ```

  Convert database datetimes to UTC RFC 3339 strings ending in `Z`. Do not return row objects, raw JSON, or unvalidated dictionaries from the repository.

- [x] **Step 4: Implement deterministic bounded reads**

  Use a shared `_bounded_first(first: int) -> int`, select `first + 1` rows ordered by primary key ascending, return at most `first`, and set `next_cursor` only when the extra row exists. Validate filters against the canonical frozen status sets. Detail methods return `None` for unknown identifiers.

- [x] **Step 5: Implement honest checkpoint lookup**

  Load a checkpoint by exact projection type. Return `None` when absent. When present, convert through `ProjectionFreshnessV1.from_dict`; do not recompute lag at request time or rewrite stored status.

- [x] **Step 6: Run repository plus migration tests**

  Run:

  ```bash
  python -m pytest tests/test_jobsearch_projection_repository.py tests/test_jobsearch_migrations.py -q
  ```

  Expected: all selected tests pass.

- [x] **Step 7: Commit Task 2**

  ```bash
  git add core/jobsearch_projections.py core/__init__.py tests/test_jobsearch_projection_repository.py
  git commit -m "feat: add contract-backed job-search projection reads" \
    -m "Co-Authored-By: OpenAI Codex <codex@openai.com>"
  ```

---

### Task 3: Expose Bounded Side-Effect-Free GraphQL Projections

**Files:**
- Create: `api/graphql/jobsearch_types.py`
- Create: `tests/test_graphql_jobsearch.py`
- Modify: `api/graphql/schema.py`

**Interfaces:**
- Consumes `JobSearchProjectionRepository`.
- Produces query fields:
  - `opportunity(id: String!): Opportunity`
  - `opportunities(first: Int = 25, after: String, status: String): OpportunityPage!`
  - `application(id: String!): Application`
  - `applications(first: Int = 25, after: String, status: String, opportunityId: String): ApplicationPage!`
  - `relationship(id: String!): Relationship`
  - `relationships(first: Int = 25, after: String, opportunityId: String): RelationshipPage!`
  - `outreachItem(id: String!): Outreach`
  - `outreach(first: Int = 25, after: String, status: String, opportunityId: String): OutreachPage!`
- Each page produces `items`, nullable `freshness`, and nullable `nextCursor`.

- [x] **Step 1: Write failing GraphQL tests**

  Execute Strawberry schema queries against the SQLite session and prove:

  ```graphql
  query {
    opportunities(first: 2, status: "qualified") {
      items {
        opportunityId
        employer
        evidenceRefs { sourceKind sourceRef commitment redactedSummary }
        freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
      }
      freshness { sourceEventPosition status }
      nextCursor
    }
  }
  ```

  Add assertions that:

  - detail and list results match seeded canonical entities;
  - applications expose ordered stage history and artifact references;
  - relationships expose only opaque `dexContactRef` plus derived relevance;
  - outreach exposes the message commitment but no body, subject, prompt, completion, note, or draft-text field;
  - empty unprojected results expose `freshness: null`;
  - `first=0` and `first=101` return GraphQL errors;
  - list queries do not produce per-item SQL;
  - `schema._schema.mutation_type is None`;
  - the authenticated mounted `/api/graphql` route can read one job-search projection.

- [x] **Step 2: Run the GraphQL test and verify RED**

  Run:

  ```bash
  python -m pytest tests/test_graphql_jobsearch.py -q
  ```

  Expected: GraphQL validation fails because the job-search query fields do not exist.

- [x] **Step 3: Define explicit Strawberry types**

  Add focused types for evidence references, freshness, application stages, all four entities, and four page wrappers. Conversion methods must accept only canonical contract dataclasses returned by the repository. Use Strawberry field names and default camel-case serialization; do not use generic `JSON` for job-search domain fields.

- [x] **Step 4: Wire repository-backed query resolvers**

  Instantiate `JobSearchProjectionRepository(info.context["db"])` inside each resolver and delegate validation, pagination, filtering, conversion, and checkpoint loading to the repository. Resolver bodies must not write, commit, enqueue, send, scrape, or call external systems.

- [x] **Step 5: Run focused GraphQL and authentication tests**

  Run:

  ```bash
  python -m pytest tests/test_graphql_jobsearch.py tests/test_graphql_operations.py tests/test_auth_boundary.py -q
  ```

  Expected: all selected tests pass and the schema still has no mutation root.

- [x] **Step 6: Commit Task 3**

  ```bash
  git add api/graphql/jobsearch_types.py api/graphql/schema.py tests/test_graphql_jobsearch.py
  git commit -m "feat: expose read-only job-search projections" \
    -m "Co-Authored-By: OpenAI Codex <codex@openai.com>"
  ```

---

### Task 4: Verify, Document, and Publish the Stacked Unit

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-22-job-search-platform-execution-manifest.md`
- Modify: `docs/superpowers/plans/2026-07-23-ultradex-jobsearch-persistence-projections.md`

**Interfaces:**
- Documents `alembic upgrade head`, startup behavior, GraphQL query names, privacy custody, nullable freshness, and stacked dependency order.

- [x] **Step 1: Document the operator and developer surface**

  Add exact commands:

  ```bash
  alembic upgrade head
  pytest -q
  ```

  State that production startup applies the versioned job-search revision after legacy bootstrap, GraphQL is read-only, raw connector content is never persisted, and the unit is stacked on PR 2 plus `ravenhelm-contracts` PR 18.

- [x] **Step 2: Run the complete Python verification gate**

  Run:

  ```bash
  python -m pytest -q
  python -m compileall -q api core sdk ultradex_sdk tests migrations
  python -m build
  python -m pip check
  git diff --check feat/jobsearch-observability-foundation...HEAD
  ```

  Expected:

  - all tests pass with exactly the one pre-existing strict MCP XFAIL;
  - compileall is silent and exits zero;
  - wheel and sdist build;
  - dependency check exits zero;
  - diff check emits no output.

- [x] **Step 3: Inspect migration and GraphQL proof boundaries**

  Confirm:

  ```bash
  python -m pytest \
    tests/test_jobsearch_migrations.py \
    tests/test_jobsearch_projection_repository.py \
    tests/test_graphql_jobsearch.py -q
  ```

  Expected: all JS-U02 migration and query tests pass independently.

- [x] **Step 4: Commit documentation and verification evidence**

  ```bash
  git add README.md docs/superpowers/plans
  git commit -m "docs: record job-search persistence verification" \
    -m "Co-Authored-By: OpenAI Codex <codex@openai.com>"
  ```

  Verification evidence recorded on 2026-07-23:

  - `python -m pytest -q`: 103 passed, one pre-existing strict MCP XFAIL.
  - `python -m compileall -q api core sdk ultradex_sdk tests migrations`: exited
    zero without output.
  - `python -m build`: built `ultradex_sdk-1.1.0.tar.gz` and
    `ultradex_sdk-1.1.0-py3-none-any.whl`.
  - `python -m pip check`: no broken requirements. The specified shared virtual
    environment initially lacked the `pip` module; `python -m ensurepip --upgrade`
    installed the bundled pip before the exact check was rerun.
  - `git diff --check feat/jobsearch-observability-foundation...HEAD`: exited zero
    without output.
  - `python -m pytest tests/test_jobsearch_migrations.py
    tests/test_jobsearch_projection_repository.py tests/test_graphql_jobsearch.py
    -q`: 60 passed.
  - Final-review RED tests independently reproduced all four gaps: in-memory
    startup omitted all five versioned tables; canonical checkpoint parity/page
    lookup checks failed for the three singular keys; outreach lacked
    item-level freshness and did not fail closed without a checkpoint; and
    `relevance_signals` remained in both ORM and migrated schema.
  - Final-review focused GREEN reruns passed 1 startup test, 5 canonical-key
    tests, 6 outreach provenance/fail-closed tests, and 1 relationship-schema
    test before the 60-test combined JS-U02 gate.

- [x] **Step 5: Obtain independent whole-unit review**

  The reviewer reports findings first and verifies:

  - migration reversibility and existing-database safety;
  - contract parity and no copied wire models;
  - absence of restricted raw-content fields;
  - checkpoint honesty;
  - deterministic pagination and bounded SQL;
  - a read-only GraphQL schema;
  - no JS-U03–JS-U08 scope.

  Independent whole-unit review at `3657dec` reports no Critical, Important, or
  Minor findings and marks the stacked unit ready to merge subject to its
  dependency order.

- [ ] **Step 6: Push and open a stacked GitHub PR**

  Push `feat/jobsearch-persistence-projections` to the personal GitHub remote and open the PR with base `feat/jobsearch-observability-foundation`. Record that the PR must not merge before PR 2 and must not be merged without explicit PR-specific approval.

---

## Self-Review

- Spec coverage: all four V1 entities, stage history, artifact references, Dex custody, outreach commitments, durable source position, projection timestamp, lag, bounded reads, private classification, and no mutation root are assigned to Tasks 1–3.
- Frozen gaps: source adapters and projector writes remain JS-U04/JS-U03; telemetry export remains JS-U07; the contract has no direct application-to-relationship reference, so V1 relationships remain opportunity-scoped without a local contract extension.
- Placeholder scan: the plan contains no unresolved placeholder, deferred code stub, or worker-selected architecture.
- Type consistency: database rows convert to canonical `ravenhelm_contracts` dataclasses, repository pages feed explicit Strawberry types, and all four list surfaces use the same nullable checkpoint and cursor contract.
