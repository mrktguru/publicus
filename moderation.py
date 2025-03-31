# moderation.py
from datetime import datetime, timedelta

posts_queue = {}

def add_post_to_queue(post_id, post_text, image_url):
    posts_queue[post_id] = {
        "post_text": post_text,
        "image_url": image_url,
        "status": "pending",
        "created_at": datetime.now(),
        "moderation_deadline": datetime.now() + timedelta(hours=24)
    }

def get_pending_posts():
    now = datetime.now()
    return {
        pid: post for pid, post in posts_queue.items()
        if post["status"] == "pending" and now >= post["moderation_deadline"]
    }
