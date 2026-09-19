import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from pathlib import Path

# Import all models so Alembic can detect them
from app.models import user, location, capture, game_world, friendship, category, tag, reconstruction_job, gameplay, upload_job, permission, role, reconstruction_metadata, visual_landmark

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.core.database import Base
target_metadata = Base.metadata

# Read DATABASE_URL from environment if not in alembic.ini
def get_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    # Fallback to config file
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    url = get_url()
    
    # For SQLite, connect_args are needed
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    
    from sqlalchemy import create_engine
    engine = create_engine(url, connect_args=connect_args)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
