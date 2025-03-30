#!/usr/bin/env python3
"""
bot.py

Пример Telegram-бота, публикующего посты об искусстве с возможностью модерации.
Посты генерируются с помощью OpenAI Chat API: OpenAI самостоятельно выбирает картину,
находит ссылку на изображение и генерирует подробное описание. Пост отправляется на модерацию администратору,
а при одобрении или по истечении 24 часов автоматически публикуется в канал.

Перед запуском:
1. Установите Python 3.8+.
2. Установите необходимые библиотеки:
   pip install python-telegram-bot==13.15 apscheduler openai python-dotenv pytz
3. Создайте файл .env в корневой директории проекта со следующим содержимым:
   TELEGRAM_BOT_TOKEN=ваш_токен_бота
   OPENAI_API_KEY=ваш_API_ключ_OpenAI
   ADMIN_CHAT_ID=ваш_Telegram_ID
   CHANNEL_ID=@имя_вашего_канала
4. Запустите скрипт: python3 bot.py
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta

import openai
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Чтение переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Например: "@art_channel"

# Настройка OpenAI
openai.api_key = OPENAI_API_KEY

# In-memory хранилище постов (для продакшена рекомендуется использовать БД)
posts_queue = {}

def generate_post():
    """
    Генерирует пост с помощью OpenAI Chat API.
    Запрос к API просит выбрать случайную известную картину, найти ссылку на изображение
    (например, с Википедии) и сгенерировать подробное описание.
    Ответ должен быть отформатирован в формате JSON с ключами 'post_text' и 'image_url'.
    """
    prompt = (
        "Ты искусствовед, специализирующийся на публикациях для Telegram-каналов об искусстве. "
        "Выбери случайную известную картину среди произведений различных художников (например, 'Девятый вал', "
        "'Звёздная ночь', 'Мона Лиза' и т.д.), и сгенерируй подробное описание, включающее заголовок, "
        "исторический контекст, интересные факты, детали картины и описание техники исполнения. "
        "Также найди ссылку на изображение высокого разрешения с надёжного источника, например, с Википедии. "
        "Отформатируй ответ в формате JSON с двумя ключами: 'post_text' и 'image_url'."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты помогаешь создавать посты об искусстве для Telegram-канала."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        response_text = response.choices[0].message['content'].strip()
        data = json.loads(response_text)
        post_text = data.get("post_text", "Ошибка: Не удалось получить описание поста.")
        image_url = data.get("image_url", "")
    except Exception as e:
        post_text = (
            "*Ошибка генерации поста*\n\n"
            "Не удалось сгенерировать пост с помощью OpenAI: " + str(e)
        )
        image_url = ""
        logger.error("Ошибка при генерации поста: %s", e)
    return post_text, image_url

def add_post_to_queue(post_id, post_text, image_url):
    """
    Добавляет сгенерированный пост в очередь модерации.
    """
    posts_queue[post_id] = {
        "post_text": post_text,
        "image_url": image_url,
        "status": "pending",  # Статусы: pending, approved, published, rejected
        "created_at": datetime.now(),
        "moderation_deadline": datetime.now() + timedelta(hours=24)
    }
    logger.info(f"Пост {post_id} добавлен в очередь на модерацию.")

def send_moderation_request(context: CallbackContext, post_id, post_text, image_url):
    """
    Отправляет пост администратору для модерации с inline-кнопками "Одобрить" и "Отклонить".
    """
    keyboard = [
        [
            InlineKeyboardButton("Одобрить", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton("Отклонить", callback_data=f"reject_{post_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"Новый пост для модерации:\n\n{post_text}"
    context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=image_url if image_url else None,
        caption=message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"Запрос на модерацию отправлен для поста {post_id}.")

def publish_post(context: CallbackContext, post_id):
    """
    Публикует пост в канал и обновляет его статус.
    """
    if post_id in posts_queue:
        post = posts_queue[post_id]
        if post["status"] not in ["published"]:
            context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=post["image_url"] if post["image_url"] else None,
                caption=post["post_text"],
                parse_mode=ParseMode.MARKDOWN
            )
            post["status"] = "published"
            logger.info(f"Пост {post_id} опубликован в канале.")

def check_pending_posts(context: CallbackContext):
    """
    Проверяет посты в очереди модерации.
    Если срок модерации истёк, пост публикуется автоматически.
    """
    now = datetime.now()
    for post_id, post in list(posts_queue.items()):
        if post["status"] == "pending" and now >= post["moderation_deadline"]:
            logger.info(f"Срок модерации поста {post_id} истёк, публикация производится автоматически.")
            publish_post(context, post_id)

def generate_and_send_post(context: CallbackContext):
    """
    Генерирует новый пост, добавляет его в очередь и отправляет на модерацию.
    Вызывается по расписанию или по команде администратора.
    """
    post_text, image_url = generate_post()
    post_id = str(int(time.time()))
    add_post_to_queue(post_id, post_text, image_url)
    send_moderation_request(context, post_id, post_text, image_url)

def start(update, context: CallbackContext):
    """
    Обработчик команды /start. Отправляет приветственное сообщение.
    """
    update.message.reply_text("Привет! Я бот, который публикует посты об искусстве. Используйте /generate для создания нового поста.")

def generate_command(update, context: CallbackContext):
    """
    Обработчик команды /generate для принудительной генерации поста.
    Доступна только администратору.
    """
    if update.message.from_user.id != ADMIN_CHAT_ID:
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    generate_and_send_post(context)
    update.message.reply_text("Пост сгенерирован и отправлен на модерацию.")

def button_handler(update, context: CallbackContext):
    """
    Обработка нажатий inline-кнопок (одобрение или отклонение поста).
    """
    query = update.callback_query
    query.answer()
    data = query.data.split("_")
    action = data[0]
    post_id = data[1]
    
    if post_id not in posts_queue:
        query.edit_message_caption(caption="Пост уже обработан или не найден.")
        return
    
    if action == "approve":
        posts_queue[post_id]["status"] = "approved"
        publish_post(context, post_id)
        query.edit_message_caption(caption="Пост одобрен и опубликован.")
    elif action == "reject":
        posts_queue[post_id]["status"] = "rejected"
        query.edit_message_caption(caption="Пост отклонён.")
        logger.info(f"Пост {post_id} отклонён администратором.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("generate", generate_command))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Создаем планировщик и указываем часовой пояс (например, московский)
    scheduler = BackgroundScheduler()
    moscow_tz = pytz.timezone("Europe/Moscow")
    scheduler.add_job(generate_and_send_post, 'cron', hour=10, minute=0, args=[updater.bot], timezone=moscow_tz)
    scheduler.add_job(check_pending_posts, 'interval', minutes=5, args=[updater.bot])
    scheduler.start()
    
    updater.start_polling()
    logger.info("Бот запущен. Для остановки нажмите Ctrl+C.")
    updater.idle()

if __name__ == '__main__':
    main()
