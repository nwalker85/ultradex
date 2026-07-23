"""Add governed job-search commands, approvals, events, and receipts.

Revision ID: 20260723_0002
Revises: 20260723_0001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0002"
down_revision: str | None = "20260723_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobsearch_commands",
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("command_id", sa.String(length=128), nullable=False),
        sa.Column("command_name", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("delegation_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("operation_id"),
        sa.UniqueConstraint("command_id"),
    )
    op.create_index(
        "ix_jobsearch_commands_command_name",
        "jobsearch_commands",
        ["command_name"],
        unique=False,
    )

    op.create_table(
        "jobsearch_evidence_refs",
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("commitment", sa.String(length=71), nullable=False),
        sa.Column("redacted_summary", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index(
        "ix_jobsearch_evidence_refs_source_kind",
        "jobsearch_evidence_refs",
        ["source_kind"],
        unique=False,
    )

    op.create_table(
        "jobsearch_approvals",
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("outreach_id", sa.String(length=64), nullable=False),
        sa.Column("message_commitment", sa.String(length=71), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("approval_id"),
    )
    op.create_index(
        "ix_jobsearch_approvals_outreach_id",
        "jobsearch_approvals",
        ["outreach_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_approvals_expires_at",
        "jobsearch_approvals",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_approvals_status",
        "jobsearch_approvals",
        ["status"],
        unique=False,
    )

    op.create_table(
        "jobsearch_lifecycle_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_jobsearch_lifecycle_events_operation_id",
        "jobsearch_lifecycle_events",
        ["operation_id"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_lifecycle_events_event_type",
        "jobsearch_lifecycle_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_jobsearch_lifecycle_events_published_at",
        "jobsearch_lifecycle_events",
        ["published_at"],
        unique=False,
    )

    op.create_table(
        "jobsearch_execution_receipts",
        sa.Column("receipt_id", sa.String(length=128), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("receipt_hash", sa.String(length=71), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("operation_id"),
    )
    op.create_index(
        "ix_jobsearch_execution_receipts_operation_id",
        "jobsearch_execution_receipts",
        ["operation_id"],
        unique=True,
    )
    op.create_index(
        "ix_jobsearch_execution_receipts_status",
        "jobsearch_execution_receipts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jobsearch_execution_receipts_status",
        table_name="jobsearch_execution_receipts",
    )
    op.drop_index(
        "ix_jobsearch_execution_receipts_operation_id",
        table_name="jobsearch_execution_receipts",
    )
    op.drop_table("jobsearch_execution_receipts")

    op.drop_index(
        "ix_jobsearch_lifecycle_events_published_at",
        table_name="jobsearch_lifecycle_events",
    )
    op.drop_index(
        "ix_jobsearch_lifecycle_events_event_type",
        table_name="jobsearch_lifecycle_events",
    )
    op.drop_index(
        "ix_jobsearch_lifecycle_events_operation_id",
        table_name="jobsearch_lifecycle_events",
    )
    op.drop_table("jobsearch_lifecycle_events")

    op.drop_index(
        "ix_jobsearch_approvals_status",
        table_name="jobsearch_approvals",
    )
    op.drop_index(
        "ix_jobsearch_approvals_expires_at",
        table_name="jobsearch_approvals",
    )
    op.drop_index(
        "ix_jobsearch_approvals_outreach_id",
        table_name="jobsearch_approvals",
    )
    op.drop_table("jobsearch_approvals")

    op.drop_index(
        "ix_jobsearch_evidence_refs_source_kind",
        table_name="jobsearch_evidence_refs",
    )
    op.drop_table("jobsearch_evidence_refs")

    op.drop_index(
        "ix_jobsearch_commands_command_name",
        table_name="jobsearch_commands",
    )
    op.drop_table("jobsearch_commands")
