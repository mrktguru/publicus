# database/models/generation_template.py
import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, Boolean, Text, Integer, String

from .base import Base


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
