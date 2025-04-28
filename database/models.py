# database/models.py
"""
Единая точка входа для всех ORM-моделей проекта.
Добавили:
  • Base (DeclarativeBase) с naming convention
  • импорты ваших моделей, чтобы они зарегистрировались на Base
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# ---------- NEW: общая база ------------------------------------------------- #
# единая naming convention, чтобы Alembic корректно создавал имена ограничений
NAMING_CONVENTION = {
    "ix":  "ix_%(column_0_label)s",
    "uq":  "uq_%(table_name)s_%(column_0_name)s",
    "ck":  "ck_%(table_name)s_%(constraint_name)s",
    "fk":  "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk":  "pk_%(table_name)s",
}


class Base(DeclarativeBase):        # <-- главное, что нужно Alembic
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---------- ВАШИ МОДЕЛИ (оставил как были) --------------------------------- #
# Ниже -- реальные классы моделей.
# Ничего менять не нужно -- просто наследуемся от Base,
# как и прежде от declarative_base().
# --------------------------------------------------------------------------- #

# пример – замените/удалите, если у вас уже есть Group, Post и т.д.
# ---------------------------------------------------------------
# from sqlalchemy import BigInteger, Column, String
#
# class Group(Base):
#     __tablename__ = "groups"
#
#     id       = Column(BigInteger, primary_key=True, autoincrement=True)
#     chat_id  = Column(BigInteger, unique=True, nullable=False)
#     title    = Column(String, nullable=False)
#
# class Post(Base):
#     __tablename__ = "posts"
#
#     id         = Column(BigInteger, primary_key=True, autoincrement=True)
#     chat_id    = Column(BigInteger, nullable=False)
#     text       = Column(String, nullable=False)
#     created_by = Column(BigInteger, nullable=False)
# ---------------------------------------------------------------

# ---------- NEW: «собираем» все модели на Base ----------------------------- #
# Чтобы Alembic видел ВСЕ таблицы, нужно импорти-ровать файлы,
# где объявлены модели.  Добавьте их по мере появления.

from .group import Group     # noqa: F401  – пример: замените на свои
from .post import Post       # noqa: F401

# (Если модели лежат в других модулях – импортируйте их аналогично)
