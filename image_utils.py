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

def find_image_yandex(query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://yandex.ru/images/search?text={query.replace(' ', '+')}"
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'lxml')
        img = soup.select_one('img.serp-item__thumb')
        if img and img.get('src', '').startswith('https'):
            return img['src']
    except Exception as e:
        logger.warning(f"Ошибка поиска в Яндексе: {e}")
    return ""

def extract_query_from_post(text):
    match = re.search(r'«(.+?)»\s+—\s+(.+?)\s+\(\d{4}\)', text)
    if match:
        return f"{match.group(2)} {match.group(1)}"
    return "картина живопись"
