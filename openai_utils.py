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
        "Выбирай **менее известные, но реально существующие** и **эмоционально сильные** картины известных художников различных эпох.\n"
        "📛 Не выдумывай названия и авторов. Используй только проверенные произведения искусства из надёжных источников, ссылки на которые есть в Wikimedia, wikiart.org, Google Arts & Culture, сайты музеев.\n"
        "❗Если ты не уверен в существовании картины — не используй её, выбери другую.\n\n"
        "Формат ответа строго JSON:\n"
        "- post_text: строка, отформатированная в Markdown для Telegram\n"
        "- image_urls: массив из 2–3 рабочих ссылок на изображения картины в высоком разрешении\n"
        "  Используй источники: Wikimedia (upload.wikimedia.org), wikiart.org, Google Arts & Culture, сайты музеев\n\n"
        "📌 Формат текста поста (post_text):\n"
        "🖼 **«Название картины» — Автор (год)**\n\n"
        "📜 Исторический контекст\n Краткий рассказ...\n\n"
        "🔍 Детали, которые вы могли не заметить\n* ...\n* ...\n\n"
        "💡 Интересные факты\n...\n\n"
        "#жанр #эпоха #техника"
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

        if content.startswith("```json"):
            match = re.search(r"```json\n(.*?)```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

        if not content.startswith("{"):
            raise ValueError("Ответ от OpenAI не начинается с JSON")

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            fixed = content.replace("\n", "\\n").replace("\t", "\\t")
            data = json.loads(fixed)

        post_text = data.get("post_text", "⚠️ Не удалось получить текст.")
        image_urls = data.get("image_urls", [])
        logger.info(f"Полученные image_urls: {image_urls}")
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

