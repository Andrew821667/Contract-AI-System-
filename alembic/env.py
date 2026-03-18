from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import Base and all models so Alembic sees the full metadata
from src.models.database import Base
from src.models.auth_models import *  # noqa: F401,F403 — register User, Session, etc.
from src.models.analyzer_models import *  # noqa: F401,F403 — register ContractRisk, ContractRecommendation, etc.

# Import all core models so Alembic sees the new tables
from src.core.identity_org.models import *  # noqa: F401,F403
from src.core.policies.models import *  # noqa: F401,F403
from src.core.tools.models import *  # noqa: F401,F403
from src.core.agents.models import *  # noqa: F401,F403
from src.core.ai_collaboration.models import *  # noqa: F401,F403
from src.core.orchestrator.models import *  # noqa: F401,F403
from src.core.workflow.models import *  # noqa: F401,F403
from src.core.collaboration.models import *  # noqa: F401,F403
from src.core.templates.models import *  # noqa: F401,F403
from src.core.integrations.models import *  # noqa: F401,F403

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from environment or config"""
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=_is_sqlite(url),
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
