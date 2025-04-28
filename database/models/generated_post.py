from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class GeneratedPost(Base):
    """
    Пост, который бот сгенерировал в рамках определённой серии.
    """

    __tablename__ = "generated_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Группа / канал, куда отправляем
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Сгенерированный текст поста
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Время, когда надо опубликовать
    publish_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Время создания
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # --- Связь с серией --------------------------------------------------
    series_id: Mapped[int] = mapped_column(
        ForeignKey("generated_series.id"),
        nullable=False,
    )
    series: Mapped["GeneratedSeries"] = relationship(
        "GeneratedSeries",
        back_populates="posts",
        lazy="selectin",
    )
