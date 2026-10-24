"""update postgis

Revision ID: c91a0e5b6d33
Revises: b7d1e4a90c22
Create Date: 2026-10-22 23:22:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c91a0e5b6d33"
down_revision: str | Sequence[str] | None = "b7d1e4a90c22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("ALTER EXTENSION postgis UPDATE"))


def downgrade() -> None:
    pass
