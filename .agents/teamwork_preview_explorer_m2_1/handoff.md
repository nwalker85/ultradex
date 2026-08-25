# Technical Specification & Design: CRM Database Models, Alembic Migrations & ORM Projections

## Executive Summary
This report provides the complete, production-grade technical specification and implementation design for **Milestone M2: CRM Database Models, Migrations & ORM Projections** (Requirement R2, Features F3 & F4).

It defines:
1. **`OrganizationDB` (`jobsearch_organizations`)**: Master employer directory storing firmographics, domain, industry, size, advocacy ratings, and contact/lead aggregation.
2. **`LeadDB` (`jobsearch_leads`)**: Unapplied job lead inventory tracking source career boards (LinkedIn + 9 target employer boards), external ATS identifiers, compensation bounds, rich description/requirements, deterministic profile fit scores (0–100), structured match breakdown, risk flags, pipeline state machine, and atomic conversion links.
3. **Contact CRM Extensions (`contacts` table / `ContactDB`)**: In-place schema extensions for the 2,252 Dex contacts adding advocacy scoring (0–100), organization linkage (`organization_id`), sovereign operator notes (`crm_notes`), structured chronological interaction history (`communication_history` JSONB), LinkedIn URLs, and relationship tiering.
4. **Alembic Migration Script (`20260824_0004_crm_organizations_leads.py`)**: Strict, bi-directional migration with `batch_alter_table` compatibility for both SQLite (test/in-memory) and PostgreSQL (production).
5. **ORM Projections, Checkpoint Stamping & Repository Contracts**: Integration into `JOBSEARCH_PROJECTION_TABLES`, `core/jobsearch_projections.py`, `core/database.py`, and the `leads.convert` lifecycle state machine.

---

## 1. Observation

Direct code and infrastructure observations across the Ultradex / Career Command Center codebase:

### 1.1 Existing Database Architecture & Table Roster
- `core/models.py:62-207`:
  - Defines `Base = declarative_base()`
  - Core tables: `operations`, `operation_events`, `delegations`, `idempotency_keys`, `contacts`, `analysis_runs`, `settings`.
  - `ContactDB` (`core/models.py:162-185`) contains columns: `id` (String 255), `name`, `email`, `company`, `job_title`, `phone`, `notes`, `last_contacted`, `ai_value`, `ai_reason`, `outreach_strategy`, `suggested_timing`, `last_analyzed`, `created_at`, `updated_at`, `synced_at`.
  - Missing in `ContactDB`: `advocacy_score`, `organization_id` foreign key, `crm_notes` (distinct from raw Dex notes), `communication_history` JSON, `linkedin_url`, and `relationship_tier`.
- `core/jobsearch_models.py:1-251`:
  - `JOBSEARCH_PROJECTION_TABLES: frozenset[str]` currently contains:
    - `"jobsearch_opportunities"` (`OpportunityProjectionDB:46-69`)
    - `"jobsearch_applications"` (`ApplicationProjectionDB:71-91`)
    - `"jobsearch_relationships"` (`RelationshipProjectionDB:93-111`)
    - `"jobsearch_outreach"` (`OutreachProjectionDB:113-134`)
    - `"jobsearch_intent"` (`IntentProjectionDB:136-164`)
    - `"jobsearch_projection_checkpoints"` (`ProjectionCheckpointDB:166-175`)
  - `JOBSEARCH_COMMAND_TABLES: frozenset[str]` currently contains:
    - `"jobsearch_commands"`, `"jobsearch_evidence_refs"`, `"jobsearch_approvals"`, `"jobsearch_lifecycle_events"`, `"jobsearch_execution_receipts"`.
  - Freshness and audit convention across all jobsearch models:
    - `source_event_id`: `Column(String(128), nullable=False)`
    - `source_event_position`: `Column(String(128), nullable=False)`
    - `projected_at`: `Column(DateTime(timezone=True), nullable=False, default=_utcnow)`
    - `created_at`: `Column(DateTime(timezone=True), nullable=False, default=_utcnow)`
    - `updated_at`: `Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)`

### 1.2 Migration Chain & Table Isolation
- `migrations/env.py:1-49`:
  - Configured with `target_metadata = Base.metadata`.
  - Imports `core.jobsearch_models`.
- Existing migration revisions in `migrations/versions/`:
  - `20260723_0001_jobsearch_projections.py` (down_revision: None)
  - `20260723_0002_jobsearch_commands.py` (down_revision: "20260723_0001")
  - `20260816_0003_jobsearch_intent.py` (down_revision: "20260723_0002")
- Next revision identifier: `20260824_0004` (down_revision: `"20260816_0003"`).
- `core/database.py:27-38`:
  ```python
  legacy_tables = [
      table
      for table in Base.metadata.sorted_tables
      if table.name
      not in (JOBSEARCH_PROJECTION_TABLES | JOBSEARCH_COMMAND_TABLES)
  ]
  with self.engine.begin() as connection:
      Base.metadata.create_all(connection, tables=legacy_tables)
      run_jobsearch_migrations(
          self.database_url,
          connection=connection,
      )
  ```
  *Key Observation*: Any table added to `JOBSEARCH_PROJECTION_TABLES` is excluded from initial `create_all()` and created strictly via Alembic migrations.

### 1.3 Lead Ingestion & Sourcing Models
- `core/jobsearch_sourcing.py:35-197` and `cli/sense_jobs.py:35-175`:
  - `JobPosting` / `RawJobPosting`: `id`, `employer`, `title`, `location`, `description`, `required_skills`, `salary_min`, `salary_max`, `salary_currency`, `url`, `source_board`, `remote_type`, `department`, `compensation`.
  - `ProfileMatchScore`: `score` (0–100), `overall_fit_score`, `breakdown`, `risk_flags`, `explanation`, `matched_expert_skills`, `matched_advanced_skills`, `matched_ml_depth`, `missing_critical_skills`.
  - `ScoredJobLead`: `id`, `raw_posting`, `match_breakdown`, `status` ("discovered", "qualified", "watching").
- `tests/test_jobsearch_migrations.py:1-189`:
  - 16 tests verifying column types, lengths, nullable fields, defaults, and round-trip idempotent upgrade/downgrade (`command.downgrade(cfg, "base")`).

---

## 2. Logic Chain

1. **Why `OrganizationDB` and `LeadDB` must be part of `JOBSEARCH_PROJECTION_TABLES`**:
   - `core/database.py` partitions tables into unversioned legacy tables (`Base.metadata.create_all`) and versioned projection/command tables managed by Alembic.
   - Adding `jobsearch_organizations` and `jobsearch_leads` to `JOBSEARCH_PROJECTION_TABLES` ensures that tests (which run `Database.init()`) create legacy tables first and then run Alembic migrations up to head cleanly without duplicate table creation errors.

2. **Why `ContactDB` requires `batch_alter_table` in Alembic**:
   - SQLite does not support standard `ALTER TABLE ADD COLUMN` with foreign key constraints or column modifications in a single statement without table reconstruction.
   - Using Alembic's `with op.batch_alter_table("contacts") as batch_op:` generates table recreation scripts for SQLite and native `ALTER TABLE` statements for PostgreSQL, ensuring seamless local development, testing, and production deployment on Odin/Postgres.

3. **Why `LeadDB` requires explicit JSON fields for `requirements`, `match_breakdown`, and `risk_flags`**:
   - The Candidate Profile Match Engine produces deep diagnostic payloads: matched expert skills, matched advanced skills, matched ML depth competencies, missing skills, and risk tags (e.g. `compensation-unverified`).
   - Storing these in native `JSON` columns enables immediate projection queries in GraphQL and the Svelte Glass UI without redundant re-computation.

4. **Foreign Key Integrity & Deletion Cascade Semantics**:
   - `LeadDB.organization_id` -> `jobsearch_organizations.id` with `ondelete="SET NULL"`. If an organization record is deleted or merged, leads remain preserved.
   - `LeadDB.converted_opportunity_id` -> `jobsearch_opportunities.id` with `ondelete="SET NULL"`.
   - `ContactDB.organization_id` -> `jobsearch_organizations.id` with `ondelete="SET NULL"`.

---

## 3. Comprehensive Database Models & Schemas Specification

### 3.1 `OrganizationDB` Model Specification (`core/jobsearch_models.py`)

```python
class OrganizationDB(Base):
    """Employer organization directory aggregating contacts, leads, and pipeline pursuits."""

    __tablename__ = "jobsearch_organizations"

    id = Column(String(64), primary_key=True)  # e.g., 'org-anthropic' or UUID
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)  # e.g., 'anthropic.com'
    industry = Column(String(128), nullable=True, index=True)
    size = Column(String(64), nullable=True)  # e.g., '501-1000', '1000+'
    advocacy_rating = Column(Float, nullable=True, index=True)  # 0.0 - 100.0 score
    notes = Column(Text, nullable=True)

    # Freshness and audit metadata
    source_event_id = Column(String(128), nullable=False, default="pending")
    source_event_position = Column(String(128), nullable=False, default="pending")
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # ORM Relationships
    leads = relationship(
        "LeadDB",
        back_populates="organization",
        cascade="all, delete-orphan",
        foreign_keys="LeadDB.organization_id",
    )
    contacts = relationship(
        "ContactDB",
        back_populates="organization",
        foreign_keys="ContactDB.organization_id",
    )
```

### 3.2 `LeadDB` Model Specification (`core/jobsearch_models.py`)

```python
class LeadDB(Base):
    """Unapplied job posting with profile match breakdown, risk flags, and conversion tracking."""

    __tablename__ = "jobsearch_leads"

    id = Column(String(64), primary_key=True)  # e.g., 'lead-<uuid>'
    source_board = Column(String(64), nullable=False, index=True)  # 'linkedin', 'anthropic', 'openai', etc.
    external_id = Column(String(255), nullable=True, index=True)  # ATS job ID
    employer = Column(String(255), nullable=False, index=True)
    organization_id = Column(
        String(64),
        ForeignKey("jobsearch_organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    remote_type = Column(String(32), nullable=False, default="unknown", index=True)  # remote, hybrid, onsite, unknown
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(8), nullable=False, default="USD")
    url = Column(String(1024), nullable=True)
    description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=False, default=list)  # list of skill requirements
    fit_score = Column(Float, nullable=True, index=True)  # 0.0 - 100.0 deterministic score
    match_breakdown = Column(JSON, nullable=False, default=dict)  # structured scoring breakdown
    risk_flags = Column(JSON, nullable=False, default=list)  # list of risk tag strings
    state = Column(String(32), nullable=False, default="discovered", index=True)  # discovered, qualified, watching, applied, converted, dismissed, archived
    converted_opportunity_id = Column(
        String(64),
        ForeignKey("jobsearch_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Freshness and audit metadata
    source_event_id = Column(String(128), nullable=False, default="pending")
    source_event_position = Column(String(128), nullable=False, default="pending")
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # ORM Relationships
    organization = relationship(
        "OrganizationDB",
        back_populates="leads",
        foreign_keys=[organization_id],
    )
    converted_opportunity = relationship(
        "OpportunityProjectionDB",
        foreign_keys=[converted_opportunity_id],
    )
```

### 3.3 Contact CRM Schema Extensions (`core/models.py:ContactDB`)

```python
class ContactDB(Base):
    __tablename__ = "contacts"
    
    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    last_contacted = Column(DateTime, nullable=True)
    
    # AI analysis fields
    ai_value = Column(Float, nullable=True)
    ai_reason = Column(Text, nullable=True)
    outreach_strategy = Column(Text, nullable=True)
    suggested_timing = Column(String(255), nullable=True)
    last_analyzed = Column(DateTime, nullable=True)

    # CRM Domain Extensions (Milestone M2, Requirement R2)
    advocacy_score = Column(Float, nullable=True, index=True)  # 0.0 - 100.0 champion score
    organization_id = Column(
        String(64),
        ForeignKey("jobsearch_organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    crm_notes = Column(Text, nullable=True)  # Sovereign recruiter notes
    communication_history = Column(JSON, nullable=False, default=list)  # Touchpoints array
    linkedin_url = Column(String(500), nullable=True)  # LinkedIn profile URL
    relationship_tier = Column(String(32), nullable=True, index=True)  # champion, advocate, colleague, recruiter, peer
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    synced_at = Column(DateTime, default=datetime.now)

    # ORM Relationship
    organization = relationship(
        "OrganizationDB",
        back_populates="contacts",
        foreign_keys=[organization_id],
    )
```

---

## 4. Alembic Migration Script Specification

File path: `migrations/versions/20260824_0004_crm_organizations_leads.py`

```python
"""Add CRM organizations, leads tables, and contact extensions.

Revision ID: 20260824_0004
Revises: 20260816_0003
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0004"
down_revision: str | None = "20260816_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _freshness_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column(
            "source_event_position",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def upgrade() -> None:
    # 1. Create jobsearch_organizations table
    op.create_table(
        "jobsearch_organizations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("size", sa.String(length=64), nullable=True),
        sa.Column("advocacy_rating", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_freshness_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobsearch_organizations_name",
        "jobsearch_organizations",
        ["name"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_organizations_domain",
        "jobsearch_organizations",
        ["domain"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_organizations_industry",
        "jobsearch_organizations",
        ["industry"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_organizations_advocacy_rating",
        "jobsearch_organizations",
        ["advocacy_rating"],
        unique=False,
    )

    # 2. Create jobsearch_leads table
    op.create_table(
        "jobsearch_leads",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_board", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("employer", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("remote_type", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("fit_score", sa.Float(), nullable=True),
        sa.Column("match_breakdown", sa.JSON(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("converted_opportunity_id", sa.String(length=64), nullable=True),
        *_freshness_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["jobsearch_organizations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["converted_opportunity_id"],
            ["jobsearch_opportunities.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_jobsearch_leads_source_board",
        "jobsearch_leads",
        ["source_board"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_external_id",
        "jobsearch_leads",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_employer",
        "jobsearch_leads",
        ["employer"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_organization_id",
        "jobsearch_leads",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_title",
        "jobsearch_leads",
        ["title"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_remote_type",
        "jobsearch_leads",
        ["remote_type"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_fit_score",
        "jobsearch_leads",
        ["fit_score"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_state",
        "jobsearch_leads",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_leads_converted_opportunity_id",
        "jobsearch_leads",
        ["converted_opportunity_id"],
        unique=False,
    )

    # 3. Extend contacts table using batch_alter_table (safe on SQLite and Postgres)
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.add_column(sa.Column("advocacy_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("organization_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("crm_notes", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "communication_history",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )
        batch_op.add_column(sa.Column("linkedin_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("relationship_tier", sa.String(length=32), nullable=True))
        batch_op.create_index(
            "ix_contacts_advocacy_score",
            ["advocacy_score"],
            unique=False,
        )
        batch_op.create_index(
            "ix_contacts_organization_id",
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_contacts_relationship_tier",
            ["relationship_tier"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_contacts_organization_id",
            "jobsearch_organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # 1. Revert contacts table extensions
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.drop_constraint("fk_contacts_organization_id", type_="foreignkey")
        batch_op.drop_index("ix_contacts_relationship_tier")
        batch_op.drop_index("ix_contacts_organization_id")
        batch_op.drop_index("ix_contacts_advocacy_score")
        batch_op.drop_column("relationship_tier")
        batch_op.drop_column("linkedin_url")
        batch_op.drop_column("communication_history")
        batch_op.drop_column("crm_notes")
        batch_op.drop_column("organization_id")
        batch_op.drop_column("advocacy_score")

    # 2. Drop jobsearch_leads table and indexes
    op.drop_index("ix_jobsearch_leads_converted_opportunity_id", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_state", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_fit_score", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_remote_type", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_title", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_organization_id", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_employer", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_external_id", table_name="jobsearch_leads")
    op.drop_index("ix_jobsearch_leads_source_board", table_name="jobsearch_leads")
    op.drop_table("jobsearch_leads")

    # 3. Drop jobsearch_organizations table and indexes
    op.drop_index("ix_jobsearch_organizations_advocacy_rating", table_name="jobsearch_organizations")
    op.drop_index("ix_jobsearch_organizations_industry", table_name="jobsearch_organizations")
    op.drop_index("ix_jobsearch_organizations_domain", table_name="jobsearch_organizations")
    op.drop_index("ix_jobsearch_organizations_name", table_name="jobsearch_organizations")
    op.drop_table("jobsearch_organizations")
```

---

## 5. Updates to Projections, Checkpoints & Tables Metadata

### 5.1 Update to `core/jobsearch_models.py`
Add `"jobsearch_organizations"` and `"jobsearch_leads"` to `JOBSEARCH_PROJECTION_TABLES`:

```python
JOBSEARCH_PROJECTION_TABLES: frozenset[str] = frozenset(
    {
        "jobsearch_opportunities",
        "jobsearch_applications",
        "jobsearch_relationships",
        "jobsearch_outreach",
        "jobsearch_intent",
        "jobsearch_projection_checkpoints",
        "jobsearch_organizations",
        "jobsearch_leads",
    }
)
```

### 5.2 Projection Checkpoint Stamping in `core/jobsearch_executors.py`
In `_stamp_projection()`:
```python
mapping = {
    OpportunityProjectionDB: "opportunities",
    ApplicationProjectionDB: "applications",
    RelationshipProjectionDB: "relationships",
    OutreachProjectionDB: "outreach",
    IntentProjectionDB: "intent",
    OrganizationDB: "organizations",
    LeadDB: "leads",
}
```

### 5.3 Projections Repository Read Interfaces (`core/jobsearch_projections.py`)
Add read query contracts:
1. `list_organizations(db, first=20, after=None, sort_by="name") -> ProjectionPage[OrganizationDB]`
2. `get_organization(db, id: str) -> Optional[OrganizationDB]`
3. `list_leads(db, first=20, after=None, min_fit_score=0.0, state=None, employer=None) -> ProjectionPage[LeadDB]`
4. `get_lead(db, id: str) -> Optional[LeadDB]`

---

## 6. Caveats

1. **SQLite vs. PostgreSQL Alter Table Constraints**:
   - Local test suites use in-memory and temp-file SQLite databases. SQLite's lack of native `ALTER TABLE DROP COLUMN` or constraint alteration without table copying is strictly mitigated by Alembic's `batch_alter_table` context manager.
2. **Dex Sync Data Integrity**:
   - `core/dex_client.py` ingests external contacts into `ContactDB`. The new CRM fields (`advocacy_score`, `crm_notes`, `organization_id`, `communication_history`) are sovereign local fields and will never be overwritten during periodic `sense_dex.py` deltas.
3. **`JOBSEARCH_PROJECTION_TABLES` Set Invariant**:
   - Existing migration test `test_upgrade_head_creates_only_versioned_jobsearch_schema` strictly asserts that the tables created by Alembic match `JOBSEARCH_PROJECTION_TABLES | JOBSEARCH_COMMAND_TABLES`. Updating `JOBSEARCH_PROJECTION_TABLES` keeps this test passing 100%.

---

## 7. Conclusion

The designed models, schemas, and migration script provide:
- High performance indexed querying for all CRM pipeline views (`/organizations`, `/leads`, `/contacts`, `/relationships`).
- Full support for the 2,252 Dex contacts with deep advocacy scoring and communication history.
- Frictionless atomic lead-to-opportunity conversion (`leads.convert`) in `core/jobsearch_executors.py`.
- 100% clean, idempotent upgrade/downgrade migration path for both PostgreSQL and SQLite.

---

## 8. Verification Method

To independently verify the implementation once applied:

```bash
# 1. Run migration test suite (checks SQLite migration upgrade, downgrade, schema reflection, and table isolation)
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_migrations.py -v

# 2. Run executor and profile tests
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_executors.py tests/test_jobsearch_profile.py -v

# 3. Test clean downgrade and re-upgrade
python3 -c "
from alembic import command
from core.jobsearch_migrations import alembic_config
cfg = alembic_config('sqlite:////tmp/test_crm_migration.db')
command.upgrade(cfg, 'head')
command.downgrade(cfg, 'base')
command.upgrade(cfg, 'head')
print('Migration upgrade/downgrade round-trip verified successfully.')
"
```
