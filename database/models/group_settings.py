# database/models/group_settings.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from .base import Base

class GroupSettings(Base):
    """Модель настроек группы/канала"""
    __tablename__ = "group_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer)  # Связь с группой
    spreadsheet_id: Mapped[str | None] = mapped_column(String, nullable=True)  # ID Google Таблицы
    spreadsheet_name: Mapped[str | None] = mapped_column(String, nullable=True)  # Название листа
    default_signature: Mapped[str | None] = mapped_column(String, nullable=True)  # Автоматическая подпись
    auto_hashtags: Mapped[str | None] = mapped_column(String, nullable=True)  # Автоматические хэштеги
    posting_timezone: Mapped[str] = mapped_column(String, default="Europe/Moscow")  # Часовой пояс для публикаций
    additional_settings: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON с доп. настройками
