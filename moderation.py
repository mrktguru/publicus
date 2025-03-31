# moderation.py
from datetime import datetime, timedelta
import logging
from telegram import ParseMode

from config import CHANNEL_ID

logger = logging.getLogger(__name__)
posts_queue = {}

def add_post_to_queue(post_id, post_text, image_url):
    posts_queue[post_id] = {
        "post_text": post_text,
        "image_url": image_url,
        "status": "pending",
        "created_at": datetime.now(),
        "moderation_deadline": datetime.now() + timedelta(hours=24)
    }

def publish_post(bot, post_id):
    post = posts_queue.get(post_id)
    if not post or post["status"] == "published":
        return
    if post["image_url"]:
        bot.send_photo(chat_id=CHANNEL_ID, photo=post["image_url"], caption=post["post_text"], parse_mode=ParseMode.MARKDOWN)
    else:
        bot.send_message(chat_id=CHANNEL_ID, text=post["post_text"], parse_mode=ParseMode.MARKDOWN)
    post["status"] = "published"

def check_pending_posts(bot):
    now = datetime.now()
    for post_id, post in list(posts_queue.items()):
        if post["status"] == "pending" and now >= post["moderation_deadline"]:
            publish_post(bot, post_id)
