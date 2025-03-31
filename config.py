# 📁 config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")
