from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import logging

from config import BOT_TOKEN

# логируем INFO
logging.basicConfig(level=logging.INFO)

from handlers import (
    start,
    group_select,
    group_settings,
    manual_post,
    auto_generation,
    moderation,
    queue,
    history,
    pending,
)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


async def main() -> None:
    # ─────── роутеры ────────────────────────────────────────────────────────────
    dp.include_router(start.router)
    dp.include_router(group_select.router)
    dp.include_router(group_settings.router)
    dp.include_router(manual_post.router)
    dp.include_router(auto_generation.router)
    dp.include_router(moderation.router)
    dp.include_router(queue.router)
    dp.include_router(history.router)
    dp.include_router(pending.router)

    # ─────── планировщик ───────────────────────────────────────────────────────
    # импорт здесь, чтобы избежать циклического импорта
    from scheduler import setup_scheduler

    setup_scheduler(scheduler)      # ← регистрируем check_scheduled_posts
    scheduler.start()

    # ─────── запуск бота ───────────────────────────────────────────────────────
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
