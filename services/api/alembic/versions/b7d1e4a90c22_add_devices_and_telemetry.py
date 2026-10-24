"""add devices and telemetry

Revision ID: b7d1e4a90c22
Revises: 67f373b25565
Create Date: 2026-10-22 23:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.services.telemetry.partitions import CREATE_UPCOMING_PARTITIONS

revision: str = "b7d1e4a90c22"
down_revision: str | Sequence[str] | None = "67f373b25565"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
    op.create_table(
        "devices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE telemetry (
                device_id BIGINT NOT NULL REFERENCES devices (id),
                location GEOGRAPHY(POINT, 4326) NOT NULL,
                "timestamp" TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (device_id, "timestamp")
            ) PARTITION BY RANGE ("timestamp")
            """
        )
    )
    op.execute(sa.text(CREATE_UPCOMING_PARTITIONS))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS telemetry"))
    op.drop_table("devices")
    op.execute(sa.text("DROP EXTENSION IF EXISTS postgis"))
