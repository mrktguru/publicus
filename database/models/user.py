# database/models/user.py
import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, Boolean, Text, String
from .base import Base


class User(Base):
    """Модель пользователя бота"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="account_owner")  # admin или account_owner
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_active: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    current_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # ID выбранного канала
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON с настройками
