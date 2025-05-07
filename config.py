# config.py
from pathlib import Path
from dotenv import load_dotenv
import os

# ──────────────────────────────────────────────────────────────
# 1. Подгружаем .env (если запускаем локально, без Docker)
# Docker‑Compose сам подставит переменные окружения,
# но load_dotenv не мешает и внутри контейнера.
# ──────────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# ──────────────────────────────────────────────────────────────
# 2. Читаем из окружения (или ставим запасное значение)
# ──────────────────────────────────────────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN")        # без дефолта - пусть ошибка, если нет
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")   # то же
DATABASE_URL    = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")

# Новые настройки для Google Sheets
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "google_credentials.json")
GOOGLE_SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", "service-account@your-project.iam.gserviceaccount.com")

# Настройки для управления пользователями
DEFAULT_ADMIN_ID = os.getenv("DEFAULT_ADMIN_ID")  # ID администратора по умолчанию
