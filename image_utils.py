# image_utils.py
import requests
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

def is_valid_image_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'image/*,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        response = requests.get(url, headers=headers, timeout=7, stream=True, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '')
        response.close()
        return response.status_code == 200 and content_type.startswith('image/')
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
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_url = f"https://yandex.ru/images/search?text={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')

        # Пробуем сначала получить src из картинок с data-src
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("https") and is_valid_image_url(src):
                logger.info(f"Найдена картинка с Яндекса: {src}")
                return src

        logger.warning("❌ Не удалось найти изображение в Яндексе.")
        return ""
    except Exception as e:
        logger.warning(f"Ошибка при поиске в Яндекс.Картинках: {e}")
        return ""

def extract_query_from_post(post_text):
    try:
        match = re.search(r'«(.+?)»\s+—\s+(.+?)\s+\((\d{4})\)', post_text)
        if match:
            title, author, year = match.groups()
            return f"{author} {title}"
    except Exception:
        pass
    return "картина живопись"
