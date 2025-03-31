# openai_utils.py
import json
import logging
import re
import os
import openai
from config import OPENAI_API_KEY
from image_utils import find_first_valid_image_url, find_image_yandex, extract_query_from_post

logger = logging.getLogger(__name__)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

USED_TITLES_PATH = "used_titles.json"

def load_used_titles():
    if os.path.exists(USED_TITLES_PATH):
        with open(USED_TITLES_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_used_titles(titles_set):
    with open(USED_TITLES_PATH, "w", encoding="utf-8") as f:
        json.dump(list(titles_set), f, ensure_ascii=False, indent=2)

def extract_title_key(post_text):
    match = re.search(r'«(.+?)»\s+—\s+(.+?)\s+\((\d{4})\)', post_text)
    if match:
        title, author, year = match.groups()
        return f"{title.strip()} — {author.strip()} ({year})"
    return None

def generate_post():
    used_titles = load_used_titles()
    prompt = (
        "Ты искусствовед, создающий познавательные посты для Telegram-канала об искусстве.\n"
        "🔍 Используй только реально существующие картины и художников.\n"
        "📛 Не выдумывай названия, авторов, годы или изображения. Проверяй факты.\n"
        "✅ Используй только источники: Wikimedia, WikiArt, Google Arts & Culture, сайты музеев.\n\n"
        "📦 Формат ответа — строго JSON:\n"
        "- post_text: строка (текст поста в Markdown)\n"
        "- image_urls: массив из 2–3 ссылок на изображения картины\n\n"
        "📌 Формат текста:\n"
        "🖼 **«Название картины» — Автор (год)**\n\n📜 ...\n\n🔍 ...\n\n💡 ...\n\n#жанр #эпоха #стиль"
    )

    for attempt in range(3):  # до 3 попыток, если повтор
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты помогаешь создавать посты об искусстве для Telegram-канала."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```json"):
                match = re.search(r"```json\n(.*?)```", content, re.DOTALL)
                if match:
                    content = match.group(1).strip()

            if not content.startswith("{"):
                raise ValueError("Ответ от OpenAI не начинается с JSON")

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Ошибка JSON: {e}. Попытка автоочистки...")
                fixed = re.sub(r'(?<!\\)\\n', '\\\\n', content)
                fixed = re.sub(r'(?<!\\)\\t', '\\\\t', fixed)
                fixed = re.sub(r"(?<!\\)\\'", "'", fixed)
                data = json.loads(fixed)

            post_text = data.get("post_text", "⚠️ Не удалось получить текст.")
            image_urls = data.get("image_urls", [])
            logger.info(f"Полученные image_urls: {image_urls}")

            # Проверка повтора
            title_key = extract_title_key(post_text)
            if not title_key:
                logger.warning("⚠️ Не удалось извлечь название картины, продолжаем...")
            elif title_key in used_titles:
                logger.info(f"🔁 Повтор: {title_key} уже использовалась, пробуем другую...")
                continue  # Следующая попытка

            image_url = find_first_valid_image_url(image_urls)
            if not image_url:
                fallback_query = extract_query_from_post(post_text)
                logger.info(f"🔍 Поиск по Яндексу по запросу: {fallback_query}")
                image_url = find_image_yandex(fallback_query)

            # Сохраняем использованное название
            if title_key:
                used_titles.add(title_key)
                save_used_titles(used_titles)

            return post_text, image_url

        except Exception as e:
            post_text = f"*Ошибка генерации поста*\n\nOpenAI: {str(e)}"
            image_url = ""
            logger.error("Ошибка при генерации поста: %s", e)
            logger.error("Содержимое ответа OpenAI: %s", content)

    return "*Ошибка: не удалось сгенерировать уникальный пост*", ""
