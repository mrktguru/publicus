# scheduler.py
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from handlers import generate_and_send_post
from moderation import get_pending_posts
from handlers import publish_post

def start_scheduler(bot):
    moscow_tz = pytz.timezone("Europe/Moscow")
    scheduler = BackgroundScheduler(timezone=moscow_tz)

    scheduler.add_job(generate_and_send_post, 'cron', hour=10, minute=0, args=[bot])
    scheduler.add_job(check_pending_posts, 'interval', minutes=5, args=[bot])

    scheduler.start()

def check_pending_posts(bot):
    for post_id in list(get_pending_posts().keys()):
        publish_post(bot, post_id)
