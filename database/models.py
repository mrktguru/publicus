# database/models.py
import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, Boolean, Text, Integer, String
from .db import Base

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

class Group(Base):
    """Модель группы/канала"""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)  # пользовательское название
    type: Mapped[str] = mapped_column(String, default="channel")  # channel или group
    added_by: Mapped[int] = mapped_column(BigInteger)  # ID пользователя, добавившего группу
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    date_added: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_post_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

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

class Post(Base):
    """Модель поста для публикации"""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)  # ID канала/группы
    text: Mapped[str] = mapped_column(Text)  # Текст поста
    media_file_id: Mapped[str | None] = mapped_column(String, nullable=True)  # ID медиа-файла в Telegram
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)  # Тип медиа: photo, video, etc.
    publish_at: Mapped[dt.datetime] = mapped_column(DateTime)  # Время публикации
    created_by: Mapped[int] = mapped_column(BigInteger)  # ID автора
    status: Mapped[str] = mapped_column(String, default="approved")  # Статус: draft, approved, sent, error
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)  # Время создания
    published: Mapped[bool] = mapped_column(Boolean, default=False)  # Опубликован ли пост
    
    # Поля для автогенерации и модерации
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False)  # Сгенерирован ли автоматически
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ID шаблона генерации
    generation_params: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON с параметрами генерации
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)  # Причина отклонения

class GeneratedSeries(Base):
    """Настройки автогенератора (prompt + расписание)"""
    __tablename__ = "generated_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt: Mapped[str] = mapped_column(Text)  # Промпт для генерации
    repeat: Mapped[str] = mapped_column(String, default="once")  # once / daily / hourly
    time: Mapped[dt.time] = mapped_column(DateTime)  # Время генерации
    post_limit: Mapped[int] = mapped_column(Integer, default=10)  # Лимит постов
    posts_generated: Mapped[int] = mapped_column(Integer, default=0)  # Количество сгенерированных постов
    moderation: Mapped[bool] = mapped_column(Boolean, default=True)  # Требуется ли модерация

class GenerationTemplate(Base):
    """Шаблоны для генерации контента с персонализированными настройками"""
    __tablename__ = "generation_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)  # ID пользователя
    chat_id: Mapped[int] = mapped_column(BigInteger)  # ID канала/группы
    
    # Основные параметры шаблона
    content_type: Mapped[str] = mapped_column(String)  # новостной, образовательный и т.д.
    themes: Mapped[str] = mapped_column(Text)  # ключевые слова/темы
    tone: Mapped[str] = mapped_column(String)  # официальный, дружелюбный и т.д.
    
    # Структура и длина
    structure: Mapped[str] = mapped_column(String)  # JSON со структурой
    length: Mapped[str] = mapped_column(String)  # короткий, средний, длинный
    
    # Количество и модерация
    post_count: Mapped[int] = mapped_column(Integer, default=1)  # Количество постов
    moderation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Модерация включена
    
    # Служебные поля
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

# Проверьте и исправьте определение поля is_active в классе GoogleSheet
class GoogleSheet(Base):
    """Модель для хранения информации о подключенных Google Sheets"""
    __tablename__ = "google_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)  # ID канала/группы
    spreadsheet_id: Mapped[str] = mapped_column(String)  # ID Google Таблицы
    sheet_name: Mapped[str] = mapped_column(String, default="Контент-план")  # Имя листа
    last_sync: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)  # Время последней синхронизации
    # ИСПРАВЛЕНИЕ: Явно указываем False как значение по умолчанию
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)  # Активно ли подключение
    created_by: Mapped[int] = mapped_column(BigInteger)  # ID создателя
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)  # Дата создания
    sync_interval: Mapped[int] = mapped_column(Integer, default=15)  # Интервал синхронизации в минутах
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON с настройками
