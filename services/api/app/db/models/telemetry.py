from datetime import datetime

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Telemetry(Base):
    """Parent table. PostgreSQL keeps hourly partitions; requests only insert into this table."""

    __tablename__ = "telemetry"
    __table_args__ = {"postgresql_partition_by": 'RANGE ("timestamp")'}

    device_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("devices.id"),
        primary_key=True,
    )
    location: Mapped[WKBElement | str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True).with_variant(String(128), "sqlite"),
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
