"""Alembic migration environment.

The database URL and the SQLAlchemy metadata are taken from the application
itself (``app.core.config`` and ``app.database.database``) so migrations always
target the same database and the same declarative ``Base`` as the running API.
"""

from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.database.database import Base, create_app_engine, engine

# Importing the models package registers every ORM model on Base.metadata.
# It is intentionally empty at this stage; autogenerate picks up models as
# later stages add them.
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The single source of truth for the schema Alembic compares against.
target_metadata = Base.metadata

# Normally the URL comes from application settings. A caller (the test suite)
# may override it via config to migrate a different database; when it does not,
# behaviour is exactly as before.
_url = config.get_main_option("sqlalchemy.url", default=None) or settings.sqlalchemy_url

# SQLite cannot ALTER most columns in place, so Alembic must rebuild tables
# via its batch mode for future schema changes to work.
_render_as_batch = _url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting to the database."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    # Reuse the application's engine for the application's own database; build a
    # matching one (same SQLite pragmas) when migrating an overridden URL.
    connectable = engine if _url == settings.sqlalchemy_url else create_app_engine(_url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_render_as_batch,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
