import pytest
from alembic import command
from ravenhelm_contracts.jobsearch_v1 import JOBSEARCH_PROJECTION_TYPES_V1
from sqlalchemy import Integer, String, create_engine, inspect

from core.database import Database
from core.jobsearch_migrations import alembic_config, run_jobsearch_migrations
from core.jobsearch_models import (
    JOBSEARCH_COMMAND_TABLES,
    JOBSEARCH_PROJECTION_TABLES,
    JOBSEARCH_PROJECTION_TYPES,
    ApplicationProjectionDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)


def _migrated_column(tmp_path, table_name, column_name):
    engine = create_engine(f"sqlite:///{tmp_path / f'{table_name}.db'}")
    run_jobsearch_migrations(str(engine.url))
    columns = inspect(engine).get_columns(table_name)
    return next(column for column in columns if column["name"] == column_name)


@pytest.mark.parametrize(
    ("model", "table_name"),
    [
        (OpportunityProjectionDB, "jobsearch_opportunities"),
        (ApplicationProjectionDB, "jobsearch_applications"),
        (RelationshipProjectionDB, "jobsearch_relationships"),
        (OutreachProjectionDB, "jobsearch_outreach"),
        (ProjectionCheckpointDB, "jobsearch_projection_checkpoints"),
    ],
)
def test_source_event_position_uses_opaque_bounded_string(
    tmp_path,
    model,
    table_name,
):
    model_type = model.__table__.c.source_event_position.type
    migrated_type = _migrated_column(
        tmp_path,
        table_name,
        "source_event_position",
    )["type"]

    assert isinstance(model_type, String)
    assert model_type.length == 128
    assert not isinstance(model_type, Integer)
    assert isinstance(migrated_type, String)
    assert migrated_type.length == 128
    assert not isinstance(migrated_type, Integer)


def test_application_next_action_uses_contract_maximum(tmp_path):
    model_type = ApplicationProjectionDB.__table__.c.next_action.type
    migrated_type = _migrated_column(
        tmp_path,
        "jobsearch_applications",
        "next_action",
    )["type"]

    assert isinstance(model_type, String)
    assert model_type.length == 500
    assert isinstance(migrated_type, String)
    assert migrated_type.length == 500


def test_projection_checkpoint_requires_explicit_measured_lag(tmp_path):
    model_column = ProjectionCheckpointDB.__table__.c.lag_ms
    migrated_column = _migrated_column(
        tmp_path,
        "jobsearch_projection_checkpoints",
        "lag_ms",
    )

    assert model_column.default is None
    assert migrated_column["default"] is None


def test_opportunity_fit_explanation_uses_contract_maximum(tmp_path):
    model_type = OpportunityProjectionDB.__table__.c.score_explanation.type
    migrated_type = _migrated_column(
        tmp_path,
        "jobsearch_opportunities",
        "score_explanation",
    )["type"]

    assert isinstance(model_type, String)
    assert model_type.length == 1000
    assert isinstance(migrated_type, String)
    assert migrated_type.length == 1000


def test_relationship_relevance_summary_uses_contract_maximum(tmp_path):
    model_type = RelationshipProjectionDB.__table__.c.relevance_reason.type
    migrated_type = _migrated_column(
        tmp_path,
        "jobsearch_relationships",
        "relevance_reason",
    )["type"]

    assert isinstance(model_type, String)
    assert model_type.length == 500
    assert isinstance(migrated_type, String)
    assert migrated_type.length == 500


def test_relationship_schema_contains_only_canonical_contract_fields(tmp_path):
    model_columns = set(RelationshipProjectionDB.__table__.columns.keys())
    engine = create_engine(f"sqlite:///{tmp_path / 'relationship-columns.db'}")
    run_jobsearch_migrations(str(engine.url))
    migrated_columns = {
        column["name"]
        for column in inspect(engine).get_columns("jobsearch_relationships")
    }

    assert "relevance_signals" not in model_columns
    assert "relevance_signals" not in migrated_columns


def test_projection_types_match_canonical_frozen_set():
    assert JOBSEARCH_PROJECTION_TYPES == JOBSEARCH_PROJECTION_TYPES_V1
    assert JOBSEARCH_PROJECTION_TYPES == frozenset(
        {"opportunities", "applications", "relationships", "outreach"}
    )


def test_upgrade_head_creates_only_versioned_jobsearch_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    run_jobsearch_migrations(str(engine.url))
    tables = set(inspect(engine).get_table_names())
    assert tables == (
        {"alembic_version"}
        | set(JOBSEARCH_PROJECTION_TABLES)
        | set(JOBSEARCH_COMMAND_TABLES)
    )


def test_upgrade_is_idempotent_and_downgrade_removes_jobsearch_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'roundtrip.db'}")
    run_jobsearch_migrations(str(engine.url))
    run_jobsearch_migrations(str(engine.url))
    cfg = alembic_config(str(engine.url))
    command.downgrade(cfg, "base")
    assert not (
        set(inspect(engine).get_table_names())
        & (set(JOBSEARCH_PROJECTION_TABLES) | set(JOBSEARCH_COMMAND_TABLES))
    )


def test_database_init_preserves_legacy_tables_and_applies_jobsearch_revision(
    tmp_path,
):
    database = Database(f"sqlite:///{tmp_path / 'startup.db'}")
    database.init()
    tables = set(inspect(database.engine).get_table_names())
    assert {"operations", "contacts"} <= tables
    assert set(JOBSEARCH_PROJECTION_TABLES) <= tables
    assert set(JOBSEARCH_COMMAND_TABLES) <= tables


def test_database_init_uses_one_connection_for_in_memory_startup():
    database = Database("sqlite:///:memory:")

    database.init()

    tables = set(inspect(database.engine).get_table_names())
    assert {"operations", "contacts"} <= tables
    assert set(JOBSEARCH_PROJECTION_TABLES) <= tables
    assert set(JOBSEARCH_COMMAND_TABLES) <= tables
