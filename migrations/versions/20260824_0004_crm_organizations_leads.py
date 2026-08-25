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

    # 3. Extend contacts table using batch_alter_table if contacts table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "contacts" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("contacts")}
        if "advocacy_score" not in existing_cols:
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
    # 1. Revert contacts table extensions if contacts table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "contacts" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("contacts")}
        if "advocacy_score" in existing_cols:
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
