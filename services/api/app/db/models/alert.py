from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import IdBase

if TYPE_CHECKING:
    from app.db.models.subscription import Subscription


class Alert(IdBase):
    __tablename__ = "alerts"

    subscription_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    message: Mapped[str] = mapped_column(String(500))

    subscription: Mapped["Subscription"] = relationship(back_populates="alerts")
