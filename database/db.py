"""
database/db.py

Создаёт асинхронный движок SQLite (aiosqlite) и фабрику сессий AsyncSessionLocal,
экспортирует их для использования в коде (бот, алембик, и т.д.).
"""

import os

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# --------------------------------------------------------------------------- #
# 1. URL базы                                                                   #
# --------------------------------------------------------------------------- #
#   • если в окружении не задана переменная DATABASE_URL,
#     используем локальный файл `bot.db` с async-драйвером aiosqlite
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")

# --------------------------------------------------------------------------- #
# 2. Базовый класс моделей                                                     #
# --------------------------------------------------------------------------- #
class Base(AsyncAttrs, DeclarativeBase):  # type: ignore[misc]
    """Общий Base для всех ORM-моделей."""
    pass


# --------------------------------------------------------------------------- #
# 3. Движок                                                                    #
# --------------------------------------------------------------------------- #
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,               # True → SQL-лог в консоль
    future=True,
)


# --------------------------------------------------------------------------- #
# 4. Фабрика сессий                                                            #
# --------------------------------------------------------------------------- #
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)

# Теперь в коде:
#     async with AsyncSessionLocal() as session:
#         ...
#
# или через middleware / депенденси передавать session в хэндлеры.

# --------------------------------------------------------------------------- #
# 5. Для совместимости                                                        #
# --------------------------------------------------------------------------- #
SessionLocal = AsyncSessionLocal