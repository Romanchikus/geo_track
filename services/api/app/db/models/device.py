from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import IdBase

if TYPE_CHECKING:
    from app.db.models.subscription import Subscription


class Device(IdBase):
    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(String(200))

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="device",
        passive_deletes=True,
    )
