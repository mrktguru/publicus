# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import logging
from zoneinfo import ZoneInfo
import asyncio

from database.db import AsyncSessionLocal
from database.models import Post

log = logging.getLogger(__name__)
# Сохраняем глобальный объект планировщика для доступа из разных функций
_scheduler = None

def setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot):
    """Регистрирует периодическую задачу проверки очереди."""
    global _scheduler
    _scheduler = scheduler
    
    # Основная проверка каждую минуту
    scheduler.add_job(
        check_scheduled_posts,
        "interval",
        seconds=60,
        args=(bot,),
        id="check_posts",
    )


async def check_scheduled_posts(bot: Bot):
    """Отправляет все post'ы, время которых пришло, и помечает их как отправленные."""
    # Получаем текущее время в разных форматах
    now_utc = datetime.now(timezone.utc)
    now_msk = datetime.now(ZoneInfo("Europe/Moscow"))
    
    log.info(f"Checking for scheduled posts at {now_utc} UTC / {now_msk} MSK")

    next_post_time = None
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем все посты из базы для диагностики
            check_q = select(Post).order_by(Post.id)
            check_result = await session.execute(check_q)
            all_posts = check_result.scalars().all()
            
            log.info(f"Total posts in database: {len(all_posts)}")
            
            # Список постов, которые скоро должны быть опубликованы
            upcoming_posts = []
            
            if all_posts:
                for p in all_posts:
                    status = "to be published" if not p.published else "already published"
                    when = f"at {p.publish_at}" if p.publish_at else "unknown time"
                    log.info(f"Post {p.id}: status={p.status}, published={p.published}, {status}, {when}")
                    
                    # Если есть неопубликованные посты, проверим, пришло ли их время
                    if p.status == "approved" and not p.published and p.publish_at:
                        # Проверим, с учетом часового пояса
                        publish_time = p.publish_at
                        
                        # Если publish_at без временной зоны, предполагаем московское время
                        if publish_time.tzinfo is None:
                            log.info(f"Post {p.id} has naive datetime, assuming MSK")
                            # Предполагаем, что время в московском часовом поясе
                            publish_time = publish_time.replace(tzinfo=ZoneInfo("Europe/Moscow"))
                            # Конвертируем в UTC для сравнения
                            publish_time_utc = publish_time.astimezone(timezone.utc)
                        else:
                            publish_time_utc = publish_time
                            
                        log.info(f"Post {p.id} publish time: {publish_time}, converted to UTC: {publish_time_utc}")
                        
                        # Проверяем, пришло ли время публикации
                        if publish_time_utc <= now_utc:
                            log.info(f"Time to publish post {p.id}!")
                            
                            try:
                                # Отправляем пост
                                if p.media_file_id:
                                    await bot.send_photo(
                                        chat_id=p.chat_id,
                                        photo=p.media_file_id,
                                        caption=p.text,
                                    )
                                    log.info(f"Sent photo post {p.id} to chat {p.chat_id}")
                                else:
                                    await bot.send_message(p.chat_id, p.text)
                                    log.info(f"Sent text post {p.id} to chat {p.chat_id}")
    
                                # Обновляем статус
                                p.status = "sent"
                                p.published = True
                                await session.commit()
                                log.info(f"Post {p.id} marked as published")
    
                            except Exception as e:
                                log.error(f"Error sending post {p.id}: {e}")
                                p.status = "error"
                                try:
                                    await session.commit()
                                except Exception as commit_err:
                                    log.error(f"Error updating post status: {commit_err}")
                        else:
                            # Еще не время публикации
                            time_left = publish_time_utc - now_utc
                            log.info(f"Post {p.id} will be published in {time_left}")
                            
                            # Если пост должен быть опубликован в ближайшие 2 минуты,
                            # добавим его в список для точного планирования
                            if time_left < timedelta(minutes=2):
                                upcoming_posts.append((p.id, publish_time_utc))
                            
                            # Отслеживаем ближайший пост для планирования
                            if next_post_time is None or publish_time_utc < next_post_time:
                                next_post_time = publish_time_utc
            
            # Планируем точную публикацию для постов в ближайшие 2 минуты
            for post_id, post_time in upcoming_posts:
                schedule_exact_publication(bot, post_id, post_time)
                
    except Exception as e:
        log.error(f"Error checking scheduled posts: {e}")


async def publish_exact_post(bot: Bot, post_id: int):
    """Публикует конкретный пост в точное время."""
    log.info(f"Publishing exact post {post_id} at {datetime.now(timezone.utc)}")
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем пост по ID
            post = await session.get(Post, post_id)
            
            if post and post.status == "approved" and not post.published:
                # Отправляем пост
                if post.media_file_id:
                    await bot.send_photo(
                        chat_id=post.chat_id,
                        photo=post.media_file_id,
                        caption=post.text,
                    )
                    log.info(f"Sent exact photo post {post.id} to chat {post.chat_id}")
                else:
                    await bot.send_message(post.chat_id, post.text)
                    log.info(f"Sent exact text post {post.id} to chat {post.chat_id}")

                # Обновляем статус
                post.status = "sent"
                post.published = True
                await session.commit()
                log.info(f"Post {post.id} marked as published (exact)")
            else:
                log.warning(f"Post {post_id} not found or already published")
                
    except Exception as e:
        log.error(f"Error publishing exact post {post_id}: {e}")


def schedule_exact_publication(bot: Bot, post_id: int, post_time: datetime):
    """Планирует публикацию поста точно в указанное время."""
    global _scheduler
    
    if _scheduler:
        # Добавляем задачу с точным временем
        job_id = f"exact_post_{post_id}"
        
        # Удаляем старую задачу с таким же ID, если она существует
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
            
        _scheduler.add_job(
            publish_exact_post,
            "date",
            run_date=post_time,
            args=(bot, post_id),
            id=job_id,
            replace_existing=True
        )
        log.info(f"Scheduled exact publication for post {post_id} at {post_time}")
    else:
        log.error("Scheduler not initialized")
