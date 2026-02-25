"""
Alembic environment configuration.

Reads the database URL from the environment (DATABASE_URL) or falls back
to the default in alembic.ini.  Imports the ORM metadata from lib/models.py
so that autogenerate can diff the models against the live schema.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Import our models so Alembic knows about all tables
from lib.models import Base  # noqa: F401

# --------------------------------------------------------------------------
# Alembic Config object (provides access to .ini values)
# --------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# Override sqlalchemy.url from environment if present
database_url = os.environ.get("DATABASE_URL") or os.environ.get("ALEMBIC_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


# --------------------------------------------------------------------------
# Offline mode — generate SQL script without a live database
# --------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL statements to stdout without connecting to the database.
    Useful for generating migration scripts for review or manual execution.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------------------------------
# Online mode — run against a live database
# --------------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure pgvector extension exists before running migrations
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
