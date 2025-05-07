# utils/text_formatter.py
import re
import html
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

def format_google_sheet_text(text):
    """
    Преобразование текста из Google Таблицы в формат HTML для Telegram.
    
    Поддерживаются следующие маркеры форматирования:
    - *Жирный текст** -> <b>Жирный текст</b>
    - __Курсив__ -> <i>Курсив</i>
    - -Подзаголовок-- -> <b>Подзаголовок</b>\n
    - [Ссылка](URL) -> <a href="URL">Ссылка</a>
    - \n -> перенос строки
    - \n\n -> пустая строка между параграфами
    
    Также поддерживаются готовые HTML-теги:
    - <b>, <i>, <u>, <s>, <a>, <pre>, <code>
    
    Args:
        text: Исходный текст из таблицы
        
    Returns:
        str: Форматированный текст для Telegram
    """
    if not text:
        return ""
    
    try:
        # Заменяем явные переносы строк
        text = text.replace('\\n', '\n')
        
        # Проверка на наличие HTML-тегов
        html_tags = ['<b>', '<i>', '<u>', '<s>', '<a', '<pre>', '<code>']
        has_html = any(tag in text for tag in html_tags)
        
        # Если уже есть HTML-теги, предполагаем что это готовый HTML
        if not has_html:
            # Обработка жирного текста: *Жирный текст**
            text = re.sub(r'\*(.*?)\*\*', r'<b>\1</b>', text)
            
            # Обработка курсива: __Курсив__
            text = re.sub(r'__(.*?)__', r'<i>\1</i>', text)
            
            # Обработка подзаголовков: -Подзаголовок--
            text = re.sub(r'\-(.*?)\-\-', r'<b>\1</b>\n', text)
            
            # Обработка ссылок: [Текст](URL)
            text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
            
            # Экранирование специальных символов HTML после замен
            text = html.escape(text, quote=False)
            
            # Восстанавливаем теги, которые мы добавили
            text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
            text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
            text = text.replace('&lt;a href=', '<a href=').replace('&lt;/a&gt;', '</a>')
        
        # Убеждаемся, что все теги закрыты правильно
        if text.count('<b>') != text.count('</b>'):
            logger.warning(f"Unclosed <b> tags in text: {text[:100]}...")
        if text.count('<i>') != text.count('</i>'):
            logger.warning(f"Unclosed <i> tags in text: {text[:100]}...")
        if text.count('<a') != text.count('</a>'):
            logger.warning(f"Unclosed <a> tags in text: {text[:100]}...")
            
        return text
    except Exception as e:
        logger.error(f"Error formatting text: {e}")
        # В случае ошибки возвращаем исходный текст
        return text

def prepare_media_urls(media_str):
    """
    Подготовка списка URL медиа-файлов из строки.
    
    Args:
        media_str: Строка с URL (разделенные запятыми)
        
    Returns:
        list: Список URL медиа-файлов
    """
    if not media_str:
        return []
    
    try:
        # Разделяем строку по запятым и удаляем пробелы
        media_urls = 
