# database/models/google_sheet.py
import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, Text, String, Integer, Index
from .base import Base

class GoogleSheet(Base):
    """Модель для хранения информации о подключенных Google Sheets"""
    __tablename__ = "google_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)  # ID канала/группы
    spreadsheet_id: Mapped[str] = mapped_column(String)  # ID Google Таблицы
    sheet_name: Mapped[str] = mapped_column(String, default="Контент-план")  # Имя листа
    last_sync: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)  # Время последней синхронизации
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # Активно ли подключение (1 вместо True)
    created_by: Mapped[int] = mapped_column(BigInteger)  # ID создателя
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)  # Дата создания
    sync_interval: Mapped[int] = mapped_column(Integer, default=15)  # Интервал синхронизации в минутах
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON с настройками
