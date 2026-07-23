"""Programmatic Alembic entry points for the job-search projections."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
