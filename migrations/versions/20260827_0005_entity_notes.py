"""Add jobsearch_entity_notes for operator annotations on CRM entities.

Revision ID: 20260827_0005
Revises: 20260824_0004
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0005"
down_revision: str | None = "20260824_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTITY_TYPES = (
    "contact",
    "organization",
    "relationship",
    "opportunity",
    "application",
    "lead",
)


def upgrade() -> None:
    op.create_table(
        "jobsearch_entity_notes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("submitted_by", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("disposition", sa.String(length=128), nullable=True),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            f"entity_type IN ({', '.join(repr(t) for t in ENTITY_TYPES)})",
            name="ck_jobsearch_entity_notes_entity_type",
        ),
    )
    op.create_index(
        "ix_jobsearch_entity_notes_entity",
        "jobsearch_entity_notes",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_entity_notes_created_at",
        "jobsearch_entity_notes",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobsearch_entity_notes_created_at", table_name="jobsearch_entity_notes")
    op.drop_index("ix_jobsearch_entity_notes_entity", table_name="jobsearch_entity_notes")
    op.drop_table("jobsearch_entity_notes")
