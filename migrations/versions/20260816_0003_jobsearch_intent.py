"""Add the workspace-scoped job-search intent projection table.

Revision ID: 20260816_0003
Revises: 20260723_0002
Create Date: 2026-08-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260816_0003"
down_revision: str | None = "20260723_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobsearch_intent",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("target_role_families", sa.JSON(), nullable=False),
        sa.Column("target_domains", sa.JSON(), nullable=False),
        sa.Column("seniority_band", sa.String(length=128), nullable=False),
        sa.Column("location_preference", sa.String(length=255), nullable=True),
        sa.Column("remote_preference", sa.String(length=32), nullable=False),
        sa.Column("employer_exclusions", sa.JSON(), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("narrative", sa.String(length=2000), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("jobsearch_intent")
