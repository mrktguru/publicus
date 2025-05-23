# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import logging
from zoneinfo import ZoneInfo
import asyncio

import re
import traceback

from database.db import AsyncSessionLocal
from database.models import Post, Group, GoogleSheet
from utils.google_sheets import GoogleSheetsClient
from utils.text_formatter import format_google_sheet_text, prepare_media_urls

log = logging.getLogger(__name__)
# Сохраняем глобальный объект планировщика для доступа из разных функций
_scheduler = None


# Добавить в начало файла scheduler.py
import aiohttp
from io import BytesIO
from utils.text_formatter import format_google_sheet_text, prepare_media_urls

async def download_image(url: str):
    """
    Загружает изображение по URL.
    
    Args:
        url: URL изображения
        
    Returns:
        BytesIO: Объект с содержимым изображения или None в случае ошибки
    """
    log.info(f"Downloading image from URL: {url}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=20) as response:
                if response.status == 200:
                    content = await response.read()
                    log.info(f"Successfully downloaded image, size: {len(content)} bytes")
                    return BytesIO(content)
                else:
                    log.error(f"Failed to download image, HTTP status: {response.status}")
                    return None
        except Exception as e:
            log.error(f"Error downloading image: {e}")
            return None


# начало загрузки изображений из URL
import aiohttp
from io import BytesIO
from utils.text_formatter import format_google_sheet_text, prepare_media_urls

async def download_image(url: str):
    """
    Загружает изображение по URL.
    
    Args:
        url: URL изображения
        
    Returns:
        BytesIO: Объект с содержимым изображения или None в случае ошибки
    """
    log.info(f"Downloading image from URL: {url}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=20) as response:
                if response.status == 200:
                    content = await response.read()
                    log.info(f"Successfully downloaded image, size: {len(content)} bytes")
                    return BytesIO(content)
                else:
                    log.error(f"Failed to download image, HTTP status: {response.status}")
                    return None
        except Exception as e:
            log.error(f"Error downloading image: {e}")
            return None
# конец загрузки изображений из URL


def setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot):
    """Регистрирует периодические задачи."""
    global _scheduler
    _scheduler = scheduler
    
    # Основная проверка каждую минуту (существующая)
    scheduler.add_job(
        check_scheduled_posts,
        "interval",
        seconds=60,
        args=(bot,),
        id="check_posts",
    )
    
    # Добавляем проверку Google Таблиц каждые 15 минут
    scheduler.add_job(
        check_google_sheets,
        "interval",
        minutes=15,
        args=(bot,),
        id="check_sheets",
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
                                log.info(f"Sending post {p.id} to chat {p.chat_id}")
                                log.info(f"Post text: {p.text[:100]}...")
                                log.info(f"Post media: {p.media_file_id}")

                                # Отправляем пост
                                if p.media_file_id:
                                    result = await bot.send_photo(
                                        chat_id=p.chat_id,
                                        photo=p.media_file_id,
                                        caption=p.text,
                                        parse_mode="HTML"
                                    )
                                    log.info(f"Sent photo post {p.id} to chat {p.chat_id}, message_id: {result.message_id}")
                                else:
                                    result = await bot.send_message(
                                        chat_id=p.chat_id, 
                                        text=p.text,
                                        parse_mode="HTML"
                                    )
                                    log.info(f"Sent text post {p.id} to chat {p.chat_id}, message_id: {result.message_id}")
    
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


# Заменить существующую функцию check_google_sheets в scheduler.py

# Заменить существующую функцию check_google_sheets в scheduler.py

async def check_google_sheets(bot: Bot):
    """Проверяет подключенные Google Таблицы на наличие запланированных постов."""
    log.info(f"Checking Google Sheets at {datetime.now(timezone.utc)}")
    
    try:
        # Инициализируем клиент Google Sheets
        sheets_client = GoogleSheetsClient()
        
        async with AsyncSessionLocal() as session:
            # Получаем все активные подключения таблиц
            sheets_q = select(GoogleSheet).filter(GoogleSheet.is_active == 1)  # Используем 1 вместо True
            sheets_result = await session.execute(sheets_q)
            active_sheets = sheets_result.scalars().all()
            
            log.info(f"Found {len(active_sheets)} active Google Sheets connections")
            
            if not active_sheets:
                log.info("No active Google Sheets connections found")
                return
            
            # Обрабатываем каждую таблицу
            for sheet in active_sheets:
                try:
                    # Обновляем время последней синхронизации
                    sheet.last_sync = datetime.now(timezone.utc)
                    
                    # Получаем запланированные посты
                    log.info(f"Getting upcoming posts from sheet {sheet.spreadsheet_id}, sheet name: {sheet.sheet_name}")
                    
                    try:
                        upcoming_posts = sheets_client.get_upcoming_posts(
                            sheet.spreadsheet_id, 
                            sheet.sheet_name
                        )
                        
                        log.info(f"Found {len(upcoming_posts)} upcoming posts in sheet {sheet.spreadsheet_id}")
                        
                        # Обрабатываем каждый пост
                        for post in upcoming_posts:
                            # Форматируем текст
                            formatted_text = format_google_sheet_text(post['text'])
                            
                            # Публикуем пост
                            try:
                                # Получаем channel_id из Telegram или из таблицы
                                channel_id = post['channel']
                                log.info(f"Post channel ID: {channel_id}")
                                
                                # Если канал указан не в формате числового ID
                                if isinstance(channel_id, str):
                                    # Если в ID есть скобки, извлекаем ID из них
                                    if '(' in channel_id and ')' in channel_id:
                                        import re
                                        match = re.search(r'\(([^)]+)\)', channel_id)
                                        if match:
                                            channel_id = match.group(1)
                                            log.info(f"Extracted channel ID from brackets: {channel_id}")
                                
                                # Проверяем, является ли ID правильным числовым форматом
                                if isinstance(channel_id, str) and not channel_id.startswith('-100'):
                                    # Это не числовой ID канала, а возможно его название
                                    # Пытаемся найти этот канал в базе данных
                                    channel_q = select(Group).filter(Group.title == channel_id)
                                    channel_result = await session.execute(channel_q)
                                    channel = channel_result.scalar_one_or_none()
                                    
                                    if channel:
                                        channel_id = channel.chat_id
                                        log.info(f"Found channel in database: {channel_id}")
                                
                                log.info(f"Final channel ID for post: {channel_id}")
                                
                                # Проверяем наличие медиа
                                if post.get('media'):
                                    # Подготавливаем URL медиа
                                    media_urls = prepare_media_urls(post['media'])
                                    log.info(f"Prepared media URLs: {media_urls}")
                                    
                                    if media_urls:
                                        # Проверяем, является ли медиа URL или file_id
                                        media_url = media_urls[0]
                                        
                                        if media_url.startswith(('http://', 'https://')):
                                            # Это URL, пробуем загрузить изображение с таймаутом
                                            try:
                                                image_data = await asyncio.wait_for(
                                                    download_image(media_url), 
                                                    timeout=30
                                                )
                                                
                                                if image_data:
                                                    # Отправляем фото
                                                    await bot.send_photo(
                                                        chat_id=channel_id,
                                                        photo=image_data,
                                                        caption=formatted_text,
                                                        parse_mode="HTML"
                                                    )
                                                    log.info(f"Sent photo from URL for post {post['id']} to channel {channel_id}")
                                                else:
                                                    # Если не удалось скачать изображение, отправляем только текст
                                                    await bot.send_message(
                                                        chat_id=channel_id,
                                                        text=formatted_text + "\n\n[Не удалось загрузить изображение]",
                                                        parse_mode="HTML"
                                                    )
                                                    log.warning(f"Failed to download image from URL, sent text only for post {post['id']}")
                                            except asyncio.TimeoutError:
                                                log.error(f"Timeout downloading image from {media_url}")
                                                await bot.send_message(
                                                    chat_id=channel_id,
                                                    text=formatted_text + "\n\n[Таймаут загрузки изображения]",
                                                    parse_mode="HTML"
                                                )
                                        else:
                                            # Вероятно, это file_id - пробуем отправить как есть
                                            try:
                                                await bot.send_photo(
                                                    chat_id=channel_id,
                                                    photo=media_url,
                                                    caption=formatted_text,
                                                    parse_mode="HTML"
                                                )
                                                log.info(f"Sent photo with file_id for post {post['id']} to channel {channel_id}")
                                            except Exception as media_err:
                                                log.error(f"Error sending photo with file_id: {media_err}")
                                                # Отправляем сообщение без медиа
                                                await bot.send_message(
                                                    chat_id=channel_id,
                                                    text=formatted_text,
                                                    parse_mode="HTML"
                                                )
                                                log.info(f"Sent text only message for post {post['id']} to channel {channel_id}")
                                    else:
                                        # Отправляем сообщение без медиа, так как нет корректных URL
                                        await bot.send_message(
                                            chat_id=channel_id,
                                            text=formatted_text,
                                            parse_mode="HTML"
                                        )
                                        log.info(f"Sent text only message (no valid media URLs) for post {post['id']} to channel {channel_id}")
                                else:
                                    # Отправляем сообщение без медиа
                                    await bot.send_message(
                                        chat_id=channel_id,
                                        text=formatted_text,
                                        parse_mode="HTML"
                                    )
                                    log.info(f"Sent text only message (no media) for post {post['id']} to channel {channel_id}")
                                
                                # Обновляем статус в таблице
                                sheets_client.update_post_status(
                                    sheet.spreadsheet_id,
                                    sheet.sheet_name,
                                    post['row_index'],
                                    "Опубликован"
                                )
                                
                                # Добавляем информацию в историю
                                sheets_client.add_to_history(
                                    sheet.spreadsheet_id,
                                    post,
                                    "Успешно"
                                )
                                
                                log.info(f"Successfully published post {post['id']} from Google Sheets")
                                
                            except Exception as e:
                                log.error(f"Error publishing post from Google Sheets: {e}")
                                
                                # Обновляем статус в таблице только если post и row_index доступны
                                if post.get('row_index'):
                                    try:
                                        sheets_client.update_post_status(
                                            sheet.spreadsheet_id,
                                            sheet.sheet_name,
                                            post['row_index'],
                                            "Ошибка"
                                        )
                                        
                                        # Добавляем информацию в историю
                                        sheets_client.add_to_history(
                                            sheet.spreadsheet_id,
                                            post,
                                            f"Ошибка: {str(e)}"
                                        )
                                    except Exception as update_err:
                                        log.error(f"Error updating post status after failure: {update_err}")
                    
                    except Exception as posts_err:
                        log.error(f"Error getting upcoming posts: {posts_err}")
                    
                except Exception as sheet_error:
                    log.error(f"Error processing sheet {sheet.spreadsheet_id}: {sheet_error}")
            
            # Сохраняем изменения в БД
            await session.commit()
            
    except Exception as e:
        log.error(f"Error checking Google Sheets: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")


async def process_sheet(sheets_client, sheet, bot):
    """Обрабатывает отдельную таблицу с тайм-аутом."""
    # Обновляем время последней синхронизации
    sheet.last_sync = datetime.now(timezone.utc)
    
    # Получаем запланированные посты с безопасной обработкой
    try:
        log.info(f"Getting posts from sheet {sheet.spreadsheet_id}")
        upcoming_posts = sheets_client.get_upcoming_posts(
            sheet.spreadsheet_id, 
            sheet.sheet_name
        )
        
        log.info(f"Found {len(upcoming_posts)} upcoming posts in sheet {sheet.spreadsheet_id}")
        
        # Обрабатываем каждый пост
        for post in upcoming_posts:
            try:
                # Все остальные операции с ограничением времени
                await process_post(sheets_client, sheet, post, bot)
            except Exception as post_error:
                log.error(f"Error processing post: {post_error}")
    except Exception as fetch_error:
        log.error(f"Error fetching posts from sheet {sheet.spreadsheet_id}: {fetch_error}")        


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
                        parse_mode="HTML"
                    )
                    log.info(f"Sent exact photo post {post.id} to chat {post.chat_id}")
                else:
                    await bot.send_message(
                        chat_id=post.chat_id, 
                        text=post.text,
                        parse_mode="HTML"
                    )
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
