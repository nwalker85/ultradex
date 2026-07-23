"""Add versioned job-search projection tables.

Revision ID: 20260723_0001
Revises:
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _freshness_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("source_event_position", sa.BigInteger(), nullable=False),
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
    op.create_table(
        "jobsearch_opportunities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("employer_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("role_family", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_explanation", sa.Text(), nullable=True),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        *_freshness_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobsearch_opportunities_state",
        "jobsearch_opportunities",
        ["state"],
        unique=False,
    )

    op.create_table(
        "jobsearch_applications",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("stage_history", sa.JSON(), nullable=False),
        sa.Column("artifact_refs", sa.JSON(), nullable=False),
        sa.Column("next_action", sa.String(length=255), nullable=True),
        sa.Column(
            "next_action_deadline",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        *_freshness_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobsearch_applications_opportunity_id",
        "jobsearch_applications",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_applications_state",
        "jobsearch_applications",
        ["state"],
        unique=False,
    )

    op.create_table(
        "jobsearch_relationships",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("dex_contact_ref", sa.String(length=255), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("relevance_reason", sa.Text(), nullable=True),
        sa.Column("relevance_signals", sa.JSON(), nullable=False),
        *_freshness_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobsearch_relationships_opportunity_id",
        "jobsearch_relationships",
        ["opportunity_id"],
        unique=False,
    )

    op.create_table(
        "jobsearch_outreach",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("relationship_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("message_commitment", sa.String(length=255), nullable=False),
        sa.Column(
            "approval_contract_ref",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("sent_evidence_ref", sa.String(length=255), nullable=True),
        *_freshness_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobsearch_outreach_opportunity_id",
        "jobsearch_outreach",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_outreach_relationship_id",
        "jobsearch_outreach",
        ["relationship_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_outreach_state",
        "jobsearch_outreach",
        ["state"],
        unique=False,
    )

    op.create_table(
        "jobsearch_projection_checkpoints",
        sa.Column("projection_type", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("source_event_position", sa.BigInteger(), nullable=False),
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("lag_ms", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("projection_type"),
    )
    op.create_index(
        "ix_jobsearch_projection_checkpoints_status",
        "jobsearch_projection_checkpoints",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jobsearch_projection_checkpoints_status",
        table_name="jobsearch_projection_checkpoints",
    )
    op.drop_table("jobsearch_projection_checkpoints")

    op.drop_index(
        "ix_jobsearch_outreach_state",
        table_name="jobsearch_outreach",
    )
    op.drop_index(
        "ix_jobsearch_outreach_relationship_id",
        table_name="jobsearch_outreach",
    )
    op.drop_index(
        "ix_jobsearch_outreach_opportunity_id",
        table_name="jobsearch_outreach",
    )
    op.drop_table("jobsearch_outreach")

    op.drop_index(
        "ix_jobsearch_relationships_opportunity_id",
        table_name="jobsearch_relationships",
    )
    op.drop_table("jobsearch_relationships")

    op.drop_index(
        "ix_jobsearch_applications_state",
        table_name="jobsearch_applications",
    )
    op.drop_index(
        "ix_jobsearch_applications_opportunity_id",
        table_name="jobsearch_applications",
    )
    op.drop_table("jobsearch_applications")

    op.drop_index(
        "ix_jobsearch_opportunities_state",
        table_name="jobsearch_opportunities",
    )
    op.drop_table("jobsearch_opportunities")
