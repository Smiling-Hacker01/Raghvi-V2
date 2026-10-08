"""Add provider-agnostic payment identifiers to subscriptions."""

from alembic import op
import sqlalchemy as sa


revision = "d6a7f90b1c42"
down_revision = "b25e23833241"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add generic provider columns to user_subscriptions
    op.add_column("user_subscriptions", sa.Column("provider_name", sa.String(50)))
    op.add_column("user_subscriptions", sa.Column("provider_subscription_id", sa.String(100)))
    op.add_column("user_subscriptions", sa.Column("provider_customer_id", sa.String(100)))
    op.add_column("user_subscriptions", sa.Column("last_provider_payment_id", sa.String(100)))
    op.create_index(
        "ix_user_sub_provider_subscription",
        "user_subscriptions",
        ["provider_name", "provider_subscription_id"],
    )
    
    # Data migration for existing Stripe records
    op.execute(
        "UPDATE user_subscriptions "
        "SET provider_name = 'stripe', "
        "provider_subscription_id = stripe_subscription_id, "
        "provider_customer_id = stripe_customer_id "
        "WHERE stripe_subscription_id IS NOT NULL OR stripe_customer_id IS NOT NULL"
    )

    # Create new payment domain tables
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("processed", sa.Boolean, default=False, nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_webhook_events_provider_name", "webhook_events", ["provider_name"])
    op.create_index("ix_webhook_events_processed", "webhook_events", ["processed"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("provider_payment_id", sa.String(100), nullable=False, unique=True),
        sa.Column("provider_subscription_id", sa.String(100), nullable=True),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, default="USD"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_payment_transactions_user_id", "payment_transactions", ["user_id"])
    op.create_index("ix_payment_transactions_provider_name", "payment_transactions", ["provider_name"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])
    op.create_index("ix_payment_transactions_subscription_id", "payment_transactions", ["provider_subscription_id"])

def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_table("webhook_events")
    
    op.drop_index("ix_user_sub_provider_subscription", table_name="user_subscriptions")
    op.drop_column("user_subscriptions", "last_provider_payment_id")
    op.drop_column("user_subscriptions", "provider_customer_id")
    op.drop_column("user_subscriptions", "provider_subscription_id")
    op.drop_column("user_subscriptions", "provider_name")
