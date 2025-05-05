# database/models.py
import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, Boolean, Text, Integer, String
from .db import Base


class Group(Base):
    __tablename__ = "groups"

    id:        Mapped[int] = mapped_column(primary_key=True)
    chat_id:   Mapped[int] = mapped_column(BigInteger, unique=True)
    title:     Mapped[str] = mapped_column(String)
    added_by:  Mapped[int] = mapped_column(BigInteger)
    date_added: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow
    )


class Post(Base):
    __tablename__ = "posts"

    id:            Mapped[int]            = mapped_column(primary_key=True)
    chat_id:       Mapped[int]            = mapped_column(BigInteger)
    text:          Mapped[str]            = mapped_column(Text)
    media_file_id: Mapped[str | None]     = mapped_column(String, nullable=True)
    publish_at:    Mapped[dt.datetime]    = mapped_column(DateTime)
    created_by:    Mapped[int]            = mapped_column(BigInteger)
    status:        Mapped[str]            = mapped_column(String, default="approved")
    created_at:    Mapped[dt.datetime]    = mapped_column(
        DateTime, default=dt.datetime.utcnow
    )
    published:     Mapped[bool]           = mapped_column(Boolean, default=False)
    
    # Новые поля для улучшенной автогенерации и модерации
    is_generated:    Mapped[bool]           = mapped_column(Boolean, default=False)
    template_id:     Mapped[int | None]     = mapped_column(Integer, nullable=True)
    generation_params: Mapped[str | None]   = mapped_column(Text, nullable=True)  # JSON с параметрами
    rejection_reason: Mapped[str | None]    = mapped_column(String, nullable=True)


class GeneratedSeries(Base):
    """Настройки автогенератора (prompt + расписание)."""

    __tablename__ = "generated_series"

    id:               Mapped[int]         = mapped_column(primary_key=True)
    prompt:           Mapped[str]         = mapped_column(Text)
    repeat:           Mapped[str]         = mapped_column(
        String, default="once"
    )  # once / daily / hourly
    time:             Mapped[dt.time]     = mapped_column(DateTime)
    post_limit:       Mapped[int]         = mapped_column(Integer, default=10)
    posts_generated:  Mapped[int]         = mapped_column(Integer, default=0)
    moderation:       Mapped[bool]        = mapped_column(Boolean, default=True)


class GenerationTemplate(Base):
    """Шаблоны для генерации контента с персонализированными настройками."""
    
    __tablename__ = "generation_templates"
    
    id:               Mapped[int]         = mapped_column(primary_key=True)
    user_id:          Mapped[int]         = mapped_column(BigInteger)
    chat_id:          Mapped[int]         = mapped_column(BigInteger)
    
    # Основные параметры шаблона
    content_type:     Mapped[str]         = mapped_column(String)  # новостной, образовательный и т.д.
    themes:           Mapped[str]         = mapped_column(Text)  # ключевые слова/темы
    tone:             Mapped[str]         = mapped_column(String)  # официальный, дружелюбный и т.д.
    
    # Структура и длина
    structure:        Mapped[str]         = mapped_column(String)  # JSON со структурой (заголовок, текст и т.д.)
    length:           Mapped[str]         = mapped_column(String)  # короткий, средний, длинный
    
    # Количество и модерация
    post_count:       Mapped[int]         = mapped_column(Integer, default=1)
    moderation_enabled: Mapped[bool]      = mapped_column(Boolean, default=True)
    
    # Служебные поля
    created_at:       Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_used_at:     Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)
