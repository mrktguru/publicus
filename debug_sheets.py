#!/usr/bin/env python3
import asyncio
import logging
from sqlalchemy import select, create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Импортируем модели
from database.db import Base
from database.models import GoogleSheet, Group, User

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# URL подключения к БД
DATABASE_URL = "sqlite+aiosqlite:///bot.db"

# Создаем асинхронный движок и сессию
async_engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def check_db_state():
    """Проверка состояния базы данных"""
    async with AsyncSessionLocal() as session:
        # Проверяем все таблицы
        sheets_q = select(GoogleSheet)
        sheets_result = await session.execute(sheets_q)
        all_sheets = sheets_result.scalars().all()
        
        print(f"Всего таблиц в БД: {len(all_sheets)}")
        for sheet in all_sheets:
            print(f"ID: {sheet.id}, Channel: {sheet.chat_id}, Active: {sheet.is_active}, "
                  f"Spreadsheet ID: {sheet.spreadsheet_id}")
        
        # Проверяем активные таблицы
        active_sheets_q = select(GoogleSheet).filter(GoogleSheet.is_active == True)
        active_sheets_result = await session.execute(active_sheets_q)
        active_sheets = active_sheets_result.scalars().all()
        
        print(f"\nАктивных таблиц: {len(active_sheets)}")
        for sheet in active_sheets:
            print(f"ID: {sheet.id}, Channel: {sheet.chat_id}, Active: {sheet.is_active}, "
                  f"Spreadsheet ID: {sheet.spreadsheet_id}")
        
        # Проверяем группы с таблицами
        channels_q = select(Group)
        channels_result = await session.execute(channels_q)
        channels = channels_result.scalars().all()
        
        print(f"\nКаналы в БД: {len(channels)}")
        for channel in channels:
            # Проверяем активные таблицы для этого канала
            channel_sheets_q = select(GoogleSheet).filter(
                GoogleSheet.chat_id == channel.chat_id,
                GoogleSheet.is_active == True
            )
            channel_sheets_result = await session.execute(channel_sheets_q)
            channel_sheets = channel_sheets_result.scalars().all()
            
            print(f"Канал: {channel.title} (ID: {channel.chat_id}), "
                  f"Активных таблиц: {len(channel_sheets)}")
            
            # Проверяем исключительно для канала Ногомяч
            if "Ногомяч" in channel.title:
                print("\n=== ДЕТАЛИ ДЛЯ КАНАЛА НОГОМЯЧ ===")
                print(f"chat_id: {channel.chat_id}")
                
                # Проверка через прямой SQL-запрос
                result = await session.execute(
                    text(f"SELECT id, is_active FROM google_sheets WHERE chat_id = {channel.chat_id}")
                )
                rows = result.fetchall()
                print(f"SQL запрос напрямую: найдено {len(rows)} строк")
                for row in rows:
                    print(f"ID: {row[0]}, is_active: {row[1]}")

async def main():
    await check_db_state()

if __name__ == "__main__":
    asyncio.run(main())
