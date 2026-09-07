"""SQLAlchemy engine, session factory, and the FastAPI session dependency."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Deterministic names for indexes and constraints. SQLite cannot drop or alter
# an unnamed constraint, so Alembic's batch mode (which rebuilds tables) needs
# every constraint to have a predictable name. This must stay fixed from the
# first migration onward: changing it later renames every existing constraint.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    """Turn on foreign-key enforcement for a new SQLite connection.

    SQLite ignores foreign keys unless this pragma is set, and the setting is
    per-connection rather than per-database, so it has to be reapplied every
    time the pool opens one. Without it ON DELETE clauses are silently inert on
    SQLite while behaving normally on PostgreSQL.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app_engine(url: str) -> Engine:
    """Build an engine configured the way this application expects.

    Tests build engines for temporary databases through this function so they
    get the same SQLite behaviour as the running application.
    """
    # check_same_thread is a SQLite-only flag; FastAPI serves requests from a
    # thread pool, so connections must be usable across threads.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    new_engine = create_engine(url, connect_args=connect_args)

    # Guarded by dialect so nothing SQLite-specific reaches a PostgreSQL engine.
    if new_engine.dialect.name == "sqlite":
        event.listen(new_engine, "connect", _enable_sqlite_foreign_keys)

    return new_engine


engine = create_app_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """The single declarative base for the project.

    Every ORM model inherits from this class, and ``Base.metadata`` is the one
    schema definition Alembic compares the database against. Do not create a
    second declarative base anywhere else.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it when the request finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
