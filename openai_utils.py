# openai_utils.py
import json
import logging
import re
import openai
from image_utils import find_first_valid_image_url, find_image_yandex, extract_query_from_post

logger = logging.getLogger(__name__)
client = None

def init_openai(api_key):
    global client
    client = openai.OpenAI(api_key=api_key)

def generate_post():
    prompt = (
        "Ты искусствовед, создающий познавательные посты для Telegram-канала об искусстве.\n"
        "Выбирай менее известные, но эмоционально сильные картины разных художников.\n"
        "Не выдумывай ссылки, а используй реальные. Если не уверен в ссылке — не добавляй.\n\n"
        "Формат ответа строго JSON:\n"
        "- post_text: форматированный текст поста (Markdown)\n"
        "- image_urls: массив из 2-3 ссылок на изображения"
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

        data = json.loads(content)
        post_text = data.get("post_text", "")
        image_urls = data.get("image_urls", [])
        image_url = find_first_valid_image_url(image_urls)
        if not image_url:
            fallback_query = extract_query_from_post(post_text)
            image_url = find_image_yandex(fallback_query)
    except Exception as e:
        logger.error(f"Ошибка при генерации: {e}")
        post_text = "⚠️ Ошибка генерации"
        image_url = ""
    return post_text, image_url
