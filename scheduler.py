# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from moderation import check_pending_posts
from openai_utils import generate_post
from handlers import send_moderation_request
import time
from moderation import add_post_to_queue

def start_scheduler(bot):
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))
    scheduler.add_job(lambda: auto_generate(bot), 'cron', hour=10)
    scheduler.add_job(lambda: check_pending_posts(bot), 'interval', minutes=5)
    scheduler.start()

def auto_generate(bot):
    post_text, image_url = generate_post()
    post_id = str(int(time.time()))
    add_post_to_queue(post_id, post_text, image_url)
    send_moderation_request(bot, post_id, post_text, image_url)
