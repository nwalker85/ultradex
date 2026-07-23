from alembic import command
from sqlalchemy import create_engine, inspect

from core.database import Database
from core.jobsearch_migrations import alembic_config, run_jobsearch_migrations
from core.jobsearch_models import (
    JOBSEARCH_PROJECTION_TABLES,
    ApplicationProjectionDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)


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


def test_database_init_preserves_legacy_tables_and_applies_jobsearch_revision(
    tmp_path,
):
    database = Database(f"sqlite:///{tmp_path / 'startup.db'}")
    database.init()
    tables = set(inspect(database.engine).get_table_names())
    assert {"operations", "contacts"} <= tables
    assert set(JOBSEARCH_PROJECTION_TABLES) <= tables
