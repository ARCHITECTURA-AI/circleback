"""add oauth and unrecognized senders

Revision ID: 9e8a5b2c9101
Revises: 0c7cc2a37599
Create Date: 2026-07-14 20:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9e8a5b2c9101'
down_revision: str | Sequence[str] | None = '0c7cc2a37599'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create oauth_tokens table
    op.create_table(
        'oauth_tokens',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=50), nullable=False),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unrecognized_senders table
    op.create_table(
        'unrecognized_senders',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('handle', sa.String(length=255), nullable=False),
        sa.Column('channel', sa.Enum('EMAIL', 'SLACK', name='channel_type', create_constraint=True), nullable=False),
        sa.Column('sample_message_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('mapped_to_person_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['mapped_to_person_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['sample_message_id'], ['messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unrecognized_senders_handle'), 'unrecognized_senders', ['handle'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_unrecognized_senders_handle'), table_name='unrecognized_senders')
    op.drop_table('unrecognized_senders')
    op.drop_table('oauth_tokens')
