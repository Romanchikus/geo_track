"""allow a device on many polygons

Revision ID: a1c4e7b92d08
Revises: 02cb448a263b
Create Date: 2026-10-23 21:50:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c4e7b92d08"
down_revision: str | Sequence[str] | None = "02cb448a263b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("subscriptions_user_id_device_id_key", "subscriptions", type_="unique")
    op.create_unique_constraint(
        "uq_subscriptions_user_device_polygon",
        "subscriptions",
        ["user_id", "device_id", "polygon_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_subscriptions_user_device_polygon", "subscriptions", type_="unique")
    op.create_unique_constraint("subscriptions_user_id_device_id_key", "subscriptions", ["user_id", "device_id"])
