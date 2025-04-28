from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class GeneratedSeries(Base):
    """
    Шаблон периодических постов, который бот генерирует
    и публикует по расписанию.
    """

    __tablename__ = "generated_series"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Группа / канал, куда публикуем
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Текст-шаблон (может содержать плейсхолдеры)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # crontab-строка или человекочитаемое (“daily”, “weekly”)
    repeat: Mapped[str] = mapped_column(String(50), nullable=False)

    # Ближайшее время публикации
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # --- Связь с постами ------------------------------------------------
    posts: Mapped[list["GeneratedPost"]] = relationship(
        "GeneratedPost",
        back_populates="series",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
