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
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


async def main():
    # регистрируем роутеры
    dp.include_router(start.router)
    dp.include_router(group_select.router)
    dp.include_router(group_settings.router)
    dp.include_router(manual_post.router)
    dp.include_router(auto_generation.router)
    dp.include_router(moderation.router)
    dp.include_router(pending.router)
    dp.include_router(queue.router)
    dp.include_router(history.router)

    # планировщик
    setup_scheduler(scheduler, bot)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
