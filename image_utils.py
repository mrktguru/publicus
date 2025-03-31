# image_utils.py
import re
import requests
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def is_valid_image_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'image/*,*/*;q=0.8'
        }
        r = requests.get(url, headers=headers, stream=True, timeout=10)
        content_type = r.headers.get('Content-Type', '')
        r.close()
        return r.status_code == 200 and content_type.startswith('image/')
    except Exception as e:
        logger.warning(f"Ошибка проверки ссылки: {e}")
        return False

def find_first_valid_image_url(urls):
    for url in urls:
        if is_valid_image_url(url):
            return url
    return ""

# прикручиваем поиск по яндексу
from bs4 import BeautifulSoup

def find_image_yandex(query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_url = f"https://yandex.ru/images/search?text={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')
        images = soup.select('img.serp-item__thumb') or soup.find_all('img')
        for img in images:
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('https'):
                logger.info(f"Найдена картинка с Яндекса: {src}")
                return src
        logger.warning("❌ Не удалось найти изображение в Яндексе.")
        return ""
    except Exception as e:
        logger.warning(f"Ошибка при поиске в Яндексе: {e}")
        return ""

def extract_query_from_post(post_text):
    try:
        match = re.search(r'«(.+?)»\s+—\s+(.+?)\s+\((\d{4})\)', post_text)
        if match:
            title, author, _ = match.groups()
            return f"{author} {title}"
    except:
        pass
    return "картина живопись"

