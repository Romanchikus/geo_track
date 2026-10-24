from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import IdBase

if TYPE_CHECKING:
    from app.db.models.subscription import Subscription


class User(IdBase):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
