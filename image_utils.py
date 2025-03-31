# image_utils.py
import requests
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}


def is_valid_image_url(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=5, stream=True)
        content_type = response.headers.get("Content-Type", "")
        logger.info(f"Ответ сервера: {response.status_code}, Content-Type: {content_type}")
        response.close()
        return response.status_code == 200 and content_type.startswith("image/")
    except Exception as e:
        logger.warning(f"Ошибка при проверке URL изображения: {e}")
        return False


def find_first_valid_image_url(urls):
    for url in urls:
        logger.info(f"Проверка image_url: {url}")
        if is_valid_image_url(url):
            logger.info(f"✅ Рабочая ссылка найдена: {url}")
            return url
    logger.warning("❌ Ни одна из ссылок не прошла проверку.")
    return ""


def find_image_yandex(query):
    try:
        logger.info(f"🔍 Яндекс-поиск по запросу: {query}")
        search_url = f"https://yandex.ru/images/search?text={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=HEADERS, timeout=7)
        soup = BeautifulSoup(response.text, "lxml")
        images = soup.select("img.serp-item__thumb, img.thumb-image")
        for img in images:
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("https"):
                logger.info(f"Найдена картинка с Яндекса: {src}")
                return src
        logger.warning("❌ Не удалось найти изображение в Яндексе.")
    except Exception as e:
        logger.warning(f"Ошибка при поиске в Яндексе: {e}")
    return ""


def extract_query_from_post(post_text):
    try:
        match = re.search(r'«(.+?)»\s+—\s+(.+?)\s+\((\d{4})\)', post_text)
        if match:
            title, author, _ = match.groups()
            return f"{author} {title}"
    except Exception as e:
        logger.warning(f"Ошибка при извлечении запроса из поста: {e}")
    return "картина живопись"
