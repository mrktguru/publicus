from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class GeneratedPost(Base):
    """
    Пост, который бот сгенерировал в рамках определённой серии.
    """
    __tablename__ = "generated_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # ← новое поле

    series_id: Mapped[int] = mapped_column(
        ForeignKey("generated_series.id"),
        nullable=False,
    )
    series: Mapped["GeneratedSeries"] = relationship(
        "GeneratedSeries",
        back_populates="posts",
        lazy="selectin",
    )
