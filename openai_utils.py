# openai_utils.py
import json
import logging
import re
import openai
from config import OPENAI_API_KEY
from image_utils import find_first_valid_image_url, find_image_yandex, extract_query_from_post

logger = logging.getLogger(__name__)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def generate_post():
    prompt = (
        "Ты искусствовед, создающий познавательные посты для Telegram-канала об искусстве.\n"
        "🔍 ВАЖНО: используй только реально существующие картины и художников.\n"
        "📛 Нельзя выдумывать названия, авторов, годы или изображения. Если ты не уверен, что картина существует — выбери другую.\n"
        "✅ Проверяй свои факты — выбирай работы, которые можно найти в источниках:\n"
        "Wikimedia (upload.wikimedia.org), WikiArt.org, Google Arts & Culture, сайты музеев (например, metmuseum.org, tate.org.uk и др.)\n\n"
        "📦 Формат ответа — строго JSON:\n"
        "- post_text: текст поста (в Markdown для Telegram)\n"
        "- image_urls: массив из 2–3 рабочих ссылок на изображения картины\n\n"
        "📌 Формат текста поста:\n"
        "🖼 **«Название картины» — Автор (год)**\n\n"
        "📜 Исторический контекст\nОписание...\n\n"
        "🔍 Детали, которые вы могли не заметить\n* ...\n* ...\n\n"
        "💡 Интересные факты\n...\n\n"
        "#жанр #эпоха #стиль"
    )

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

        # Вырезаем JSON, если обёрнут в блок ```json
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

        # Проверка на источники
        if image_urls and all(
            "wikiart.org" not in url and
            "upload.wikimedia.org" not in url and
            "google.com/culturalinstitute" not in url and
            "metmuseum.org" not in url and
            "tate.org.uk" not in url
            for url in image_urls
        ):
            raise ValueError("⚠️ Все ссылки не из надёжных источников. Возможен фейк.")

        image_url = find_first_valid_image_url(image_urls)
        if not image_url:
            fallback_query = extract_query_from_post(post_text)
            logger.info(f"🔍 Поиск по Яндексу по запросу: {fallback_query}")
            image_url = find_image_yandex(fallback_query)

    except Exception as e:
        post_text = f"*Ошибка генерации поста*\n\nOpenAI: {str(e)}"
        image_url = ""
        logger.error("Ошибка при генерации поста: %s", e)
        logger.error("Содержимое ответа OpenAI: %s", content)
    return post_text, image_url
