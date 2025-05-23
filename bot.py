# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from scheduler import setup_scheduler

from sqlalchemy import text, select
from database.db import AsyncSessionLocal
from database.models import GoogleSheet

# роутеры
from handlers import (
    start,
    group_select,
    group_settings,
    manual_post,
    auto_generation,
    moderation,
    pending,
    queue,
    history,
    users,
    channels,
    google_sheets,
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


# Добавьте перед async def main():
async def fix_sheets_on_startup():
    """Исправляет проблемы с таблицей google_sheets при запуске бота"""
    logging.info("Проверка и исправление таблицы google_sheets...")
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем наличие активных таблиц с неправильным значением is_active
            problem_sheets_q = select(GoogleSheet).filter(
                GoogleSheet.is_active.is_not(None),  # не NULL
                GoogleSheet.is_active != 0,         # не 0
                GoogleSheet.is_active != 1          # не 1
            )
            problem_sheets = (await session.execute(problem_sheets_q)).scalars().all()
            
            if problem_sheets:
                logging.warning(f"Найдено {len(problem_sheets)} записей с неправильным значением is_active")
                for sheet in problem_sheets:
                    logging.info(f"Исправление записи {sheet.id}: is_active={sheet.is_active} (тип: {type(sheet.is_active)})")
                    # Исправляем значение
                    sheet.is_active = 0
                
                await session.commit()
                logging.info("Все проблемные записи исправлены")
                
    except Exception as e:
        logging.error(f"Ошибка при исправлении таблицы: {e}")
        import traceback
        logging.error(traceback.format_exc())


async def main():
    # регистрируем роутеры
    dp.include_router(start.router)
    dp.include_router(users.router)
    dp.include_router(channels.router)
    dp.include_router(manual_post.router)
    dp.include_router(google_sheets.router)
    dp.include_router(group_select.router)
    dp.include_router(group_settings.router)
    dp.include_router(queue.router)
    dp.include_router(history.router)
    dp.include_router(auto_generation.router)
    dp.include_router(moderation.router)
    dp.include_router(pending.router)

    # планировщик
    setup_scheduler(scheduler, bot)
    scheduler.start()

    await dp.start_polling(bot)
    await fix_sheets_on_startup()



if __name__ == "__main__":
    asyncio.run(main())
