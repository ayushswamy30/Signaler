"""SQLAlchemy ORM models.

This package is the registration point for the schema. A model class only
attaches itself to ``Base.metadata`` when the module defining it is imported,
so anything not imported here is invisible to both the application and to
Alembic autogenerate -- which would silently produce an empty migration.

To add a model in a later stage:

1. Create the module, e.g. ``app/models/user.py``, with a class inheriting
   from ``app.database.database.Base``.
2. Import the class below and add its name to ``__all__``.

Alembic imports this package in ``alembic/env.py`` before reading
``Base.metadata``, so step 2 is what makes a new table visible to migrations.

"""

from app.models.user import User

__all__ = ["User"]
