from pathlib import Path
from dotenv import load_dotenv          # ← новая строка
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
BOT_TOKEN       = os.getenv("BOT_TOKEN")        # без дефолта ‑ пусть ошибка, если нет
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")   # то же
DATABASE_URL    = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")
