from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.models import Base
import core.jobsearch_models  # noqa: F401


config = context.config
target_metadata = Base.metadata

# alembic.ini pins sqlalchemy.url to a local sqlite file for standalone/local
# use. In deployed environments the app is wired to DATABASE_URL (see
# core/database.py / api/main.py), and without this override alembic would
# silently migrate the sqlite default while the app opens a different
# database entirely. When DATABASE_URL is set, it takes precedence.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    # configparser treats "%" as interpolation syntax; escape it the same
    # way core/jobsearch_migrations.py does before handing the url to Config.
    config.set_main_option("sqlalchemy.url", _database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
