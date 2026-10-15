"""Add connected_accounts, communication_items, action_proposals, and meeting_notes tables.

Revision ID: e7f1a2b3c4d5
Revises: d6a7f90b1c42
Create Date: 2026-10-14 14:25:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7f1a2b3c4d5"
down_revision = "d6a7f90b1c42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. connected_accounts table
    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("account_label", sa.String(length=100), nullable=False),
        sa.Column("identifier", sa.String(length=150), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connected_accounts_user_id", "connected_accounts", ["user_id"])
    op.create_index("ix_conn_user_type", "connected_accounts", ["user_id", "account_type"])
    op.create_index("ix_conn_user_active", "connected_accounts", ["user_id", "is_active"])
    op.create_index("ix_conn_user_label", "connected_accounts", ["user_id", "account_label"])

    # 2. communication_items table
    op.create_table(
        "communication_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("sender", sa.String(length=150), nullable=False),
        sa.Column("sender_name", sa.String(length=100), nullable=False),
        sa.Column("recipient", sa.String(length=150), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.String(length=100), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("account_label", sa.String(length=100), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_communication_items_user_id", "communication_items", ["user_id"])
    op.create_index("ix_communication_items_thread_id", "communication_items", ["thread_id"])
    op.create_index("ix_communication_items_account_id", "communication_items", ["account_id"])
    op.create_index("ix_comm_user_channel_read", "communication_items", ["user_id", "channel", "is_read"])
    op.create_index("ix_comm_user_sender", "communication_items", ["user_id", "sender_name"])
    op.create_index("ix_comm_user_account", "communication_items", ["user_id", "account_id"])

    # 3. action_proposals table
    op.create_table(
        "action_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'awaiting_confirmation'")),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_proposals_user_id", "action_proposals", ["user_id"])

    # 4. meeting_notes table
    op.create_table(
        "meeting_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("meeting_date", sa.DateTime(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("raw_transcript", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_decisions", sa.JSON(), nullable=False),
        sa.Column("discussion_points", sa.JSON(), nullable=False),
        sa.Column("action_items", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("uncertainty_notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_notes_user_id", "meeting_notes", ["user_id"])
    op.create_index("ix_meeting_notes_user_date", "meeting_notes", ["user_id", "meeting_date"])
    op.create_index("ix_meeting_notes_user_deleted", "meeting_notes", ["user_id", "deleted_at"])


def downgrade() -> None:
    op.drop_table("meeting_notes")
    op.drop_table("action_proposals")
    op.drop_table("communication_items")
    op.drop_table("connected_accounts")
