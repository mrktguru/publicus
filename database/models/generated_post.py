import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, DateTime, Text, String, Boolean, ForeignKey
from .base import Base            # или .db import Base — у вас может быть иначе

class GeneratedPost(Base):
    __tablename__ = "generated_posts"

    id:          Mapped[int]          = mapped_column(primary_key=True)
    series_id:   Mapped[int]          = mapped_column(ForeignKey("generated_series.id"))
    chat_id:     Mapped[int]          = mapped_column(BigInteger)
    text:        Mapped[str]          = mapped_column(Text)
    media_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    publish_at:  Mapped[dt.datetime]  = mapped_column(DateTime)
    status:      Mapped[str]          = mapped_column(String, default="pending")
    created_at:  Mapped[dt.datetime]  = mapped_column(DateTime, default=dt.datetime.utcnow)
    published:  Mapped[bool]         = mapped_column(Boolean, default=False)


    series_id: Mapped[int] = mapped_column(
        ForeignKey("generated_series.id"),
        nullable=False,
    )
    series: Mapped["GeneratedSeries"] = relationship(
        "GeneratedSeries",
        back_populates="posts",
        lazy="selectin",
    )
