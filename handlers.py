# handlers.py
import time
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.utils.helpers import escape_markdown
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from config import ADMIN_CHAT_ID, CHANNEL_ID
from openai_utils import generate_post
from moderation import add_post_to_queue, posts_queue

logger = logging.getLogger(__name__)

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
        logger.warning("Недопустимый image_url, отправляю без фото.")
        context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=safe_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )

def publish_post(bot, post_id):
    if post_id in posts_queue:
        post = posts_queue[post_id]
        if post["status"] != "published":
            safe_text = escape_markdown(post["post_text"], version=2)
            if post["image_url"]:
                bot.send_photo(chat_id=CHANNEL_ID, photo=post["image_url"], caption=safe_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                bot.send_message(chat_id=CHANNEL_ID, text=safe_text, parse_mode=ParseMode.MARKDOWN_V2)
            post["status"] = "published"

def generate_and_send_post(context: CallbackContext):
    post_text, image_url = generate_post()
    post_id = str(int(time.time()))
    add_post_to_queue(post_id, post_text, image_url)
    send_moderation_request(context, post_id, post_text, image_url)

def start(update, context):
    update.message.reply_text("Привет! Я бот, который публикует посты об искусстве. Используйте /generate для создания нового поста.")

def generate_command(update, context):
    if update.message.from_user.id != ADMIN_CHAT_ID:
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    generate_and_send_post(context)
    update.message.reply_text("Пост сгенерирован и отправлен на модерацию.")

def button_handler(update, context):
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
        publish_post(context.bot, post_id)
        query.edit_message_caption(caption="Пост одобрен и опубликован.")
    elif action == "reject":
        posts_queue[post_id]["status"] = "rejected"
        query.edit_message_caption(caption="Пост отклонён.")
        logger.info(f"Пост {post_id} отклонён администратором.")

def register_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("generate", generate_command))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
