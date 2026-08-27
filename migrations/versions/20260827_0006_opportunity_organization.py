"""Link opportunities to organizations (employer directory).

Revision ID: 20260827_0006
Revises: 20260827_0005
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0006"
down_revision: str | None = "20260827_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobsearch_opportunities") as batch_op:
        batch_op.add_column(
            sa.Column("organization_id", sa.String(length=64), nullable=True),
        )
        batch_op.create_index(
            "ix_jobsearch_opportunities_organization_id",
            ["organization_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_jobsearch_opportunities_organization_id",
            "jobsearch_organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Backfill: case-insensitive employer_name -> organization.name
    op.execute(
        """
        UPDATE jobsearch_opportunities
        SET organization_id = (
            SELECT org.id
            FROM jobsearch_organizations AS org
            WHERE lower(trim(jobsearch_opportunities.employer_name)) = lower(trim(org.name))
            LIMIT 1
        )
        WHERE organization_id IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("jobsearch_opportunities") as batch_op:
        batch_op.drop_constraint(
            "fk_jobsearch_opportunities_organization_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_jobsearch_opportunities_organization_id")
        batch_op.drop_column("organization_id")
