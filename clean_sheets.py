# clean_sheets.py
import asyncio
import logging
from sqlalchemy import text
from database.db import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_google_sheets_table():
    """Полная очистка таблицы google_sheets"""
    async with AsyncSessionLocal() as session:
        try:
            # Выполняем прямой DELETE запрос
            await session.execute(text("DELETE FROM google_sheets"))
            await session.commit()
            logger.info("Таблица google_sheets успешно очищена")
        except Exception as e:
            logger.error(f"Ошибка при очистке таблицы: {e}")

if __name__ == "__main__":
    asyncio.run(clean_google_sheets_table())
