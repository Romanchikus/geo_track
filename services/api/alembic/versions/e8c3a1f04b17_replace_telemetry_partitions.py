"""replace telemetry partitions

Revision ID: e8c3a1f04b17
Revises: c91a0e5b6d33
Create Date: 2026-10-22 23:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.services.telemetry.partitions import CREATE_UPCOMING_PARTITIONS

revision: str = "e8c3a1f04b17"
down_revision: str | Sequence[str] | None = "c91a0e5b6d33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                child TEXT;
            BEGIN
                FOR child IN
                    SELECT c.relname
                    FROM pg_inherits AS i
                    JOIN pg_class AS c ON c.oid = i.inhrelid
                    JOIN pg_class AS parent ON parent.oid = i.inhparent
                    WHERE parent.relname = 'telemetry'
                      AND c.relname ~ '^telemetry_[0-9]+$'
                LOOP
                    EXECUTE format('DROP TABLE IF EXISTS %I', child);
                END LOOP;
            END $$;
            """
        )
    )
    op.execute(sa.text(CREATE_UPCOMING_PARTITIONS))


def downgrade() -> None:
    pass
