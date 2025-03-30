#!/usr/bin/env python3
"""
Telegram-бот, публикующий посты об искусстве с помощью OpenAI API (v1+)
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
import re

import openai
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.utils.helpers import escape_markdown
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

client = openai.OpenAI(api_key=OPENAI_API_KEY)
posts_queue = {}

def generate_post():
    prompt = (
        "Ты искусствовед, создающий познавательные посты для Telegram-канала об искусстве.\n"
        "Выбирай менее известные, но эмоционально сильные картины разных художников, стран и эпох.\n"
        "Избегай избитых работ: «Мона Лиза», «Звёздная ночь», «Девятый вал» и т.п.\n\n"
        "Отформатируй результат строго в виде JSON со следующими ключами:\n"
        "- post_text (строка): текст поста, отформатированный в Markdown для Telegram.\n"
        "- image_url (строка): ссылка на изображение в хорошем разрешении (желательно с Википедии).\n\n"
        "📌 Формат post_text должен быть таким:\n"
        "🖼 **«Название картины» — Автор (год)**\n\n"
        "📜 Исторический контекст\n"
        "Краткое, живое описание — кто автор, когда и почему написал, контекст эпохи.\n\n"
        "🔍 Детали, которые вы могли не заметить\n"
        "* Первая деталь\n"
        "* Вторая деталь\n"
        "* Третья деталь\n\n"
        "💡 Интересные факты\n"
        "Что делает картину особенной: техника, сюжет, влияние, мнение современников и т.д.\n\n"
        "#жанр #стиль #эпоха\n\n"
        "⚠️ Важно:\n"
        "- Используй markdown Telegram: жирный текст, списки, emoji.\n"
        "- Не добавляй лишний текст, объяснения, рамки — только JSON.\n"
        "- Не используй вымышленных художников или картин.\n"
        "- Не повторяй одного художника подряд."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты помогаешь создавать посты об искусстве для Telegram-канала."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=700
        )
        content = response.choices[0].message.content.strip()

        if content.startswith("```json"):
            match = re.search(r"```json\n(.*?)```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

        if not content.startswith("{"):
            raise ValueError("Ответ от OpenAI не начинается с JSON")

        data = json.loads(content)
        post_text = data.get("post_text", "⚠️ Не удалось получить текст.")
        image_url = data.get("image_url", "")

    except Exception as e:
        post_text = f"*Ошибка генерации поста*\n\nOpenAI: {str(e)}"
        image_url = ""
        logger.error("Ошибка при генерации поста: %s", e)
        logger.error("Содержимое ответа OpenAI: %s", content)
    return post_text, image_url

def send_moderation_request(context: CallbackContext, post_id, post_text, image_url):
    keyboard = [[
        InlineKeyboardButton("Одобрить", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton("Отклонить", callback_data=f"reject_{post_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"Новый пост для модерации:\n\n{post_text}"
    safe_text = escape_markdown(message, version=2)

    if image_url:
        context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=image_url,
            caption=safe_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
    else:
        context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=safe_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
    logger.info(f"Запрос на модерацию отправлен для поста {post_id}.")

def publish_post(context: CallbackContext, post_id):
    if post_id in posts_queue:
        post = posts_queue[post_id]
        if post["status"] != "published":
            safe_text = escape_markdown(post["post_text"], version=2)
            if post["image_url"]:
                context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=post["image_url"],
                    caption=safe_text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=safe_text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            post["status"] = "published"
            logger.info(f"Пост {post_id} опубликован в канале.")

def check_pending_posts(context: CallbackContext):
    now = datetime.now()
    for post_id, post in list(posts_queue.items()):
        if post["status"] == "pending" and now >= post["moderation_deadline"]:
            logger.info(f"Срок модерации поста {post_id} истёк, публикуем автоматически.")
            publish_post(context, post_id)

def add_post_to_queue(post_id, post_text, image_url):
    posts_queue[post_id] = {
        "post_text": post_text,
        "image_url": image_url,
        "status": "pending",
        "created_at": datetime.now(),
        "moderation_deadline": datetime.now() + timedelta(hours=24)
    }

def generate_and_send_post(context: CallbackContext):
    post_text, image_url = generate_post()
    post_id = str(int(time.time()))
    add_post_to_queue(post_id, post_text, image_url)
    send_moderation_request(context, post_id, post_text, image_url)

def start(update, context: CallbackContext):
    update.message.reply_text("Привет! Я бот, который публикует посты об искусстве. Используйте /generate для создания нового поста.")

def generate_command(update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_CHAT_ID:
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    generate_and_send_post(context)
    update.message.reply_text("Пост сгенерирован и отправлен на модерацию.")

def button_handler(update, context: CallbackContext):
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
    updater = Updater(
        TELEGRAM_BOT_TOKEN,
        use_context=True,
        request_kwargs={'connect_timeout': 10, 'read_timeout': 30}
    )
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("generate", generate_command))
    dp.add_handler(CallbackQueryHandler(button_handler))

    moscow_tz = pytz.timezone("Europe/Moscow")
    scheduler = BackgroundScheduler(timezone=moscow_tz)
    scheduler.add_job(generate_and_send_post, 'cron', hour=10, minute=0, args=[updater.bot])
    scheduler.add_job(check_pending_posts, 'interval', minutes=5, args=[updater.bot])
    scheduler.start()

    updater.start_polling()
    logger.info("Бот запущен. Для остановки нажмите Ctrl+C. Спасибо!")
    updater.idle()

if __name__ == '__main__':
    main()
