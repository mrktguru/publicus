from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Post(Base):
    """Сообщение, запланированное или уже отправленное ботом."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # куда публикуем
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # сам текст поста
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # file_id (фото/видео/док) из Telegram, если есть
    media_file_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # запланированное время публикации (UTC)
    publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # автор (user_id Telegram) — как BigInt
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # “draft” | “scheduled” | “sent” …
    status: Mapped[str] = mapped_column(String(20), default="draft")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    published: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- примеры связей -------------------------------------------------
    # group      = relationship("Group", back_populates="posts", lazy="joined")
    # attachments = relationship("Attachment", back_populates="post")
