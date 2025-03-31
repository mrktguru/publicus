# handlers.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from config import ADMIN_CHAT_ID
from moderation import add_post_to_queue, publish_post, posts_queue
from openai_utils import generate_post
import time

def start(update, context):
    update.message.reply_text("Привет! Я бот-публикатор искусства.")

def generate(update, context):
    if update.message.from_user.id != ADMIN_CHAT_ID:
        return update.message.reply_text("У вас нет прав.")
    post_text, image_url = generate_post()
    post_id = str(int(time.time()))
    add_post_to_queue(post_id, post_text, image_url)
    send_moderation_request(context, post_id, post_text, image_url)
    update.message.reply_text("Пост отправлен на модерацию.")

def send_moderation_request(context, post_id, post_text, image_url):
    buttons = [[
        InlineKeyboardButton("Одобрить", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton("Отклонить", callback_data=f"reject_{post_id}")
    ]]
    markup = InlineKeyboardMarkup(buttons)
    if image_url:
        context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=image_url, caption=post_text, parse_mode='Markdown', reply_markup=markup)
    else:
        context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=post_text, parse_mode='Markdown', reply_markup=markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    action, post_id = query.data.split('_', 1)
    if post_id not in posts_queue:
        query.edit_message_caption(caption="Пост не найден.")
        return
    if action == "approve":
        posts_queue[post_id]["status"] = "approved"
        publish_post(context.bot, post_id)
        query.edit_message_caption(caption="✅ Пост опубликован.")
    elif action == "reject":
        posts_queue[post_id]["status"] = "rejected"
        query.edit_message_caption(caption="❌ Пост отклонён.")

def register_handlers(dp):
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("generate", generate))
    dp.add_handler(CallbackQueryHandler(button))
