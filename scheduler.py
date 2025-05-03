# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timezone
from sqlalchemy import select
import logging

from database.db import SessionLocal
from database.models import Post

log = logging.getLogger(__name__)


def setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot):
    """Регистрирует периодическую задачу проверки очереди."""
    scheduler.add_job(
        check_scheduled_posts,
        "interval",
        seconds=60,        # проверяем каждую минуту
        args=(bot,),
        id="check_posts",
    )


async def check_scheduled_posts(bot: Bot):
    """Отправляет все post'ы, время которых пришло, и помечает их как отправленные."""
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        q = (
            select(Post)
            .where(
                Post.status == "approved",
                Post.publish_at <= now,
                Post.published.is_(False),
            )
            .order_by(Post.publish_at)
        )
        posts = (await session.execute(q)).scalars().all()

        for post in posts:
            try:
                if post.media_file_id:
                    await bot.send_photo(
                        chat_id=post.chat_id,
                        photo=post.media_file_id,
                        caption=post.text,
                    )
                else:
                    await bot.send_message(post.chat_id, post.text)

                post.status = "sent"
                post.published = True
                await session.commit()
                log.info("Post %s sent", post.id)

            except Exception as e:
                log.error("Error sending post %s: %s", post.id, e)
                post.status = "error"
                await session.commit()
