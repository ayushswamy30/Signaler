"""SQLAlchemy engine, session factory, and the FastAPI session dependency."""

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
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

# check_same_thread is a SQLite-only flag; FastAPI serves requests from a
# thread pool, so connections must be usable across threads.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)

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
