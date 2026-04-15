"""018: hash access tokens in user_sessions

Replace plaintext access_token column with access_token_hash (SHA-256).
Existing sessions are invalidated (hash cannot be back-computed from JWT).

Revision ID: 018_hash_access_tokens
Revises: 017_contract_type_index
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "018_hash_access_tokens"
down_revision = "017_contract_type_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new hash column (nullable first, then fill, then set NOT NULL)
    op.add_column(
        "user_sessions",
        sa.Column("access_token_hash", sa.String(64), nullable=True),
    )

    # Existing sessions cannot be migrated (no way to hash already-issued tokens).
    # Revoke all existing sessions — users will need to log in again.
    op.execute("UPDATE user_sessions SET revoked = TRUE WHERE revoked = FALSE")

    # Set a placeholder hash for the NOT NULL constraint
    op.execute("UPDATE user_sessions SET access_token_hash = 'revoked' WHERE access_token_hash IS NULL")

    # Now enforce NOT NULL and add unique index
    op.alter_column("user_sessions", "access_token_hash", nullable=False)
    op.create_index("ix_user_sessions_access_token_hash", "user_sessions", ["access_token_hash"], unique=True)

    # Drop old plaintext column and its index
    op.drop_index("ix_user_sessions_access_token", table_name="user_sessions")
    op.drop_column("user_sessions", "access_token")


def downgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column("access_token", sa.String(500), nullable=True),
    )
    op.execute("UPDATE user_sessions SET access_token = 'migrated_' || id")
    op.alter_column("user_sessions", "access_token", nullable=False)
    op.create_index("ix_user_sessions_access_token", "user_sessions", ["access_token"], unique=True)
    op.drop_index("ix_user_sessions_access_token_hash", table_name="user_sessions")
    op.drop_column("user_sessions", "access_token_hash")
