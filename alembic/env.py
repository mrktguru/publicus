# alembic/env.py

from __future__ import annotations

import os
import sys
import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

# ======================================================================
# 1. Добавляем путь к корню проекта в sys.path
# ======================================================================
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# ======================================================================
# 2. Импортируем MetaData всех моделей
# ======================================================================
from database.db import engine as async_engine  # AsyncEngine приложения
from database.models import Base                # declarative_base()
from database.models import User, Group, GoogleSheet
# ======================================================================


# Получаем URL из конфига
config = context.config
alembic_config = config.get_section(config.config_ini_section)
original_url = alembic_config.get("sqlalchemy.url")

# Если URL не найден, вызываем ошибку
if not original_url:
    raise ValueError("Не задан sqlalchemy.url в alembic.ini")

# Конвертируем async-URL в sync-URL
SYNC_DATABASE_URL = str(
    make_url(original_url).set(drivername="sqlite")
)

# ----------------------------------------------------------------------
# OFF-line режим — Alembic формирует SQL-файл без подключения к БД
# ----------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=SYNC_DATABASE_URL,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

# ----------------------------------------------------------------------
# ON-line режим — прямое подключение к БД и выполнение миграций
# ----------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        {"sqlalchemy.url": SYNC_DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=True,  # важно для SQLite
        )

        with context.begin_transaction():
            context.run_migrations()

# ----------------------------------------------------------------------
#  Запускаем подходящую процедуру
# ----------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
