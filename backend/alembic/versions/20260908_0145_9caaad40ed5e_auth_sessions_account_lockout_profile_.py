"""auth sessions, account lockout, profile about, participant mute

The two new NOT NULL columns carry a server_default so existing rows get a
value when the column is added. Server defaults are not part of the model
definition and are not compared by ``alembic check``, so leaving them in place
causes no drift; they simply mean a row inserted outside the ORM is still valid.

Revision ID: 9caaad40ed5e
Revises: a7cf82233bf7
Create Date: 2026-09-08 01:45:04.383721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Custom column types (e.g. UtcDateTime) are rendered by autogenerate as
# fully-qualified names, so the module must be imported here or the migration
# fails with NameError when it runs.
import app.models.types


# revision identifiers, used by Alembic.
revision: str = '9caaad40ed5e'
down_revision: Union[str, None] = 'a7cf82233bf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', app.models.types.UtcDateTime(timezone=True), nullable=False),
    sa.Column('created_at', app.models.types.UtcDateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', app.models.types.UtcDateTime(timezone=True), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_refresh_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash'))
    )
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_refresh_tokens_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('conversation_participants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('muted', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_foreign_key(batch_op.f('fk_conversation_participants_last_read_message_id_messages'), 'messages', ['last_read_message_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('about', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('locked_until', app.models.types.UtcDateTime(timezone=True), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_login_attempts')
        batch_op.drop_column('about')

    with op.batch_alter_table('conversation_participants', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_conversation_participants_last_read_message_id_messages'), type_='foreignkey')
        batch_op.drop_column('muted')

    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_user_id'))

    op.drop_table('refresh_tokens')
