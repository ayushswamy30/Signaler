"""baseline empty schema

Establishes the starting point of the migration history. The application
defines no tables yet, so this revision is intentionally empty; every
future schema change chains from it.

Revision ID: 20007824416c
Revises: 
Create Date: 2026-09-07 11:43:16.399424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20007824416c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
