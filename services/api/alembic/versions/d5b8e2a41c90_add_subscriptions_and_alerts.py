"""add subscriptions and alerts

Revision ID: d5b8e2a41c90
Revises: e8c3a1f04b17
Create Date: 2026-10-23 00:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5b8e2a41c90"
down_revision: str | Sequence[str] | None = "e8c3a1f04b17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "device_id"),
    )
    op.create_index("ix_subscriptions_device_id", "subscriptions", ["device_id"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_subscription_id", "alerts", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_subscription_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_subscriptions_device_id", table_name="subscriptions")
    op.drop_table("subscriptions")
