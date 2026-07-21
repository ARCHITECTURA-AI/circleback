"""add multi-tenancy users table and user_id columns

Revision ID: a3b4c5d6e7f8
Revises: 9e8a5b2c9101
Create Date: 2026-07-21 08:00:00.000000

Creates the `users` table and adds `user_id` FK columns to all existing
tables for multi-tenant data isolation. Also adds `sender_handle` to
messages (missing from initial migration) and fixes the
`external_message_id` unique constraint to be scoped per-user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = '9e8a5b2c9101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sentinel user for backfilling existing rows
SENTINEL_USER_ID = '00000000-0000-0000-0000-000000000001'
SENTINEL_EMAIL = 'legacy@circleback.internal'


def upgrade() -> None:
    """Upgrade schema."""

    # ── 1. Create users table ────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

    # ── 2. Insert sentinel user for backfill ─────────────────
    op.execute(
        f"INSERT INTO users (id, email, display_name) "
        f"VALUES ('{SENTINEL_USER_ID}', '{SENTINEL_EMAIL}', 'Legacy User')"
    )

    # ── 3. Add user_id columns to all existing tables ────────

    # persons
    op.add_column('persons', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.execute(f"UPDATE persons SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('persons', 'user_id', nullable=False)
    op.create_foreign_key('fk_persons_user_id', 'persons', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # threads
    op.add_column('threads', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.execute(f"UPDATE threads SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('threads', 'user_id', nullable=False)
    op.create_foreign_key('fk_threads_user_id', 'threads', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # messages — also add sender_handle (missing from initial migration)
    op.add_column('messages', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.add_column('messages', sa.Column('sender_handle', sa.String(length=255), nullable=True))
    op.execute(f"UPDATE messages SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('messages', 'user_id', nullable=False)
    op.create_foreign_key('fk_messages_user_id', 'messages', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # Fix external_message_id: drop global unique index, add per-user unique constraint
    op.drop_index('ix_messages_external_message_id', table_name='messages')
    op.create_index('ix_messages_external_message_id', 'messages', ['external_message_id'], unique=False)
    op.create_unique_constraint('uq_user_external_message', 'messages', ['user_id', 'external_message_id'])

    # commitments
    op.add_column('commitments', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.execute(f"UPDATE commitments SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('commitments', 'user_id', nullable=False)
    op.create_foreign_key('fk_commitments_user_id', 'commitments', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # eval_labels
    op.add_column('eval_labels', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.execute(f"UPDATE eval_labels SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('eval_labels', 'user_id', nullable=False)
    op.create_foreign_key('fk_eval_labels_user_id', 'eval_labels', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # oauth_tokens — add user_id + unique constraint on (user_id, provider)
    op.add_column('oauth_tokens', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.execute(f"UPDATE oauth_tokens SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('oauth_tokens', 'user_id', nullable=False)
    op.create_foreign_key('fk_oauth_tokens_user_id', 'oauth_tokens', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('uq_user_provider', 'oauth_tokens', ['user_id', 'provider'])

    # unrecognized_senders
    op.add_column('unrecognized_senders', sa.Column('user_id', sa.UUID(as_uuid=False), nullable=True))
    op.execute(f"UPDATE unrecognized_senders SET user_id = '{SENTINEL_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('unrecognized_senders', 'user_id', nullable=False)
    op.create_foreign_key('fk_unrecognized_senders_user_id', 'unrecognized_senders', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""

    # ── Remove user_id FKs and columns in reverse order ──────

    # unrecognized_senders
    op.drop_constraint('fk_unrecognized_senders_user_id', 'unrecognized_senders', type_='foreignkey')
    op.drop_column('unrecognized_senders', 'user_id')

    # oauth_tokens
    op.drop_constraint('uq_user_provider', 'oauth_tokens', type_='unique')
    op.drop_constraint('fk_oauth_tokens_user_id', 'oauth_tokens', type_='foreignkey')
    op.drop_column('oauth_tokens', 'user_id')

    # eval_labels
    op.drop_constraint('fk_eval_labels_user_id', 'eval_labels', type_='foreignkey')
    op.drop_column('eval_labels', 'user_id')

    # commitments
    op.drop_constraint('fk_commitments_user_id', 'commitments', type_='foreignkey')
    op.drop_column('commitments', 'user_id')

    # messages — restore global unique index, drop per-user constraint
    op.drop_constraint('uq_user_external_message', 'messages', type_='unique')
    op.drop_index('ix_messages_external_message_id', table_name='messages')
    op.create_index('ix_messages_external_message_id', 'messages', ['external_message_id'], unique=True)
    op.drop_constraint('fk_messages_user_id', 'messages', type_='foreignkey')
    op.drop_column('messages', 'sender_handle')
    op.drop_column('messages', 'user_id')

    # threads
    op.drop_constraint('fk_threads_user_id', 'threads', type_='foreignkey')
    op.drop_column('threads', 'user_id')

    # persons
    op.drop_constraint('fk_persons_user_id', 'persons', type_='foreignkey')
    op.drop_column('persons', 'user_id')

    # ── Drop users table ─────────────────────────────────────
    op.drop_table('users')
