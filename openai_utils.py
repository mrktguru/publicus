# openai_utils.py
import json
import logging
import re
import openai
from config import OPENAI_API_KEY
from image_utils import find_first_valid_image_url

logger = logging.getLogger(__name__)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def generate_post():
    prompt = (
        "Ты искусствовед, создающий познавательные посты для Telegram-канала об искусстве.\n"
        "Выбирай менее известные, но эмоционально сильные картины разных художников, стран и эпох.\n"
        "Избегай избитых работ: «Мона Лиза», «Звёздная ночь», «Девятый вал» и т.п.\n\n"
        "Отформатируй результат строго в виде JSON со следующими ключами:\n"
        "- post_text (строка): текст поста, отформатированный в Markdown для Telegram.\n"
        "- image_urls (массив): список из 2-3 ссылок на картину в высоком разрешении.\n"
        "  В первую очередь используй изображения с Wikimedia (upload.wikimedia.org), затем wikiart.org, Google Arts & Culture, сайты музеев.\n"
        "  Убедись, что хотя бы одна ссылка ведёт на рабочий .jpg/.png файл.\n\n"
        "📌 Формат post_text должен быть таким:\n"
        "🖼 **«Название картины» — Автор (год)**\n\n"
        "📜 Исторический контекст\nОписание...\n\n"
        "🔍 Детали, которые вы могли не заметить\n* ...\n* ...\n* ...\n\n"
        "💡 Интересные факты\nОписание...\n\n"
        "#жанр #стиль #эпоха"
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

    except Exception as e:
        post_text = f"*Ошибка генерации поста*\n\nOpenAI: {str(e)}"
        image_url = ""
        logger.error("Ошибка при генерации поста: %s", e)
        logger.error("Содержимое ответа OpenAI: %s", content)
    return post_text, image_url
