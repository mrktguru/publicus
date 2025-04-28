from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.db import AsyncSessionLocal
from database.models import Post, GeneratedPost
from datetime import datetime
from zoneinfo import ZoneInfo                    # ← добавлено
from bot import bot
from sqlalchemy import select


def setup_scheduler(scheduler: AsyncIOScheduler):
    scheduler.add_job(check_scheduled_posts, "interval", seconds=30)


async def check_scheduled_posts():
    async with AsyncSessionLocal() as session:
        now = datetime.now(ZoneInfo("Europe/Moscow"))    # ← исправлено

        # Обработка ручных постов
        result = await session.execute(
            select(Post).where(Post.publish_at <= now, Post.published == False)
        )
        for post in result.scalars().all():
            await bot.send_message(post.chat_id, post.text)
            post.published = True
            post.status = "published"
            post.published_at = now

        # Обработка автогенерированных постов
        result = await session.execute(
            select(GeneratedPost).where(
                GeneratedPost.publish_at <= now,
                GeneratedPost.published == False,
                GeneratedPost.status.in_(["approved", "auto_approved"]),
            )
        )
        for post in result.scalars().all():
            await bot.send_message(post.series.chat_id, post.text)
            post.published = True
            post.status = "published"
            post.published_at = now

        await session.commit()
