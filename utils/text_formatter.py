# utils/text_formatter.py

import re
import logging

logger = logging.getLogger(__name__)

def format_google_sheet_text(text):
    """
    Форматирует текст из Google Sheets для публикации в Telegram.
    Заменяет стандартные форматы на HTML-форматирование Telegram.
    
    Args:
        text: Исходный текст из таблицы
        
    Returns:
        str: Форматированный текст для Telegram
    """
    if not text:
        return ""
        
    # Замена \n на перенос строки
    formatted_text = text.replace('\\n', '\n')
    
    # Заменяем простое форматирование на HTML
    formatted_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', formatted_text)  # **жирный**
    formatted_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted_text)      # *курсив*
    formatted_text = re.sub(r'__(.*?)__', r'<u>\1</u>', formatted_text)      # __подчеркнутый__
    formatted_text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', formatted_text)      # ~~зачеркнутый~~
    
    # Замена URL на ссылки
    url_pattern = r'(?<![\w\d])https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?[-\w&=%./]*)?(?:#[\w-]*)?'
    formatted_text = re.sub(url_pattern, r'<a href="\g<0>">\g<0></a>', formatted_text)
    
    return formatted_text

def prepare_media_urls(media_text):
    """
    Обрабатывает содержимое ячейки медиа и извлекает URL изображений.
    
    Args:
        media_text: Текст из ячейки медиа
        
    Returns:
        list: Список URL изображений
    """
    if not media_text:
        return []
        
    # Разделяем по новым строкам или запятым (для нескольких URL)
    separators = ['\n', ',', ';']
    urls = []
    
    # Пробуем разные разделители
    for sep in separators:
        if sep in media_text:
            urls = [url.strip() for url in media_text.split(sep) if url.strip()]
            break
    else:
        # Если разделители не найдены, считаем, что это один URL
        urls = [media_text.strip()]
    
    # Отбираем только валидные URL
    valid_urls = []
    for url in urls:
        if url.startswith(('http://', 'https://')):
            valid_urls.append(url)
        else:
            logger.warning(f"Invalid URL format: {url}")
    
    return valid_urls
