# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from scheduler import setup_scheduler

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

# Исправленная функция clear_fsm_cache
async def clear_fsm_cache():
    """Очистка кешированных состояний FSM"""
    try:
        # В aiogram 3.x MemoryStorage имеет другую структуру
        if hasattr(dp.storage, 'storage'):
            dp.storage.storage.clear()
            logging.info("FSM memory storage cache cleared")
        else:
            logging.info("Storage does not have a 'storage' attribute, trying direct clearing")
            # Обходим всех пользователей и чаты
            storage_records = {}  # Заглушка, т.к. нельзя получить все записи напрямую
            logging.info("Cannot directly clear memory storage in aiogram 3.x")
    except Exception as e:
        logging.error(f"Error clearing FSM cache: {e}")

async def main():
    # Очищаем кеш перед добавлением роутеров
    await clear_fsm_cache()
    
    # Инициализируем новый диспетчер, чтобы избежать проблем с подключениями
    global dp
    dp = Dispatcher(storage=MemoryStorage())
    
    # регистрируем роутеры к новому диспетчеру
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


if __name__ == "__main__":
    asyncio.run(main())
