from typing import TYPE_CHECKING

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement, WKTElement
from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import IdBase

if TYPE_CHECKING:
    from app.db.models.alert import Alert
    from app.db.models.device import Device
    from app.db.models.user import User


class Polygon(IdBase):
    __tablename__ = "polygons"

    polygon: Mapped[WKBElement | WKTElement | str] = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326, spatial_index=True).with_variant(String(128), "sqlite")
    )

    # relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="polygon", passive_deletes=True)


class Subscription(IdBase):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", "polygon_id", name="uq_subscriptions_user_device_polygon"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    device_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("devices.id", ondelete="CASCADE"),
        index=True,
    )
    polygon_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("polygons.id", ondelete="CASCADE"), index=True)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    device: Mapped["Device"] = relationship(back_populates="subscriptions")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="subscription", passive_deletes=True)
    polygon: Mapped["Polygon"] = relationship(back_populates="subscriptions")
