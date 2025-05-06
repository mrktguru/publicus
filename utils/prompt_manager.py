# utils/prompt_manager.py
import json
from typing import Dict, List, Any, Optional
import logging

# Константы для режимов
PRO_MODE = "PRO"
BASIC_MODE = "BASIC"

# Максимальная длина промпта
MAX_PROMPT_LENGTH = 2000

# Запрещенные слова/темы (пример)
FORBIDDEN_KEYWORDS = ["взлом", "запрещенный контент", "нелегальный"]

# Настройки системного контекста
SYSTEM_CONTEXT = "Ты помощник для создания контента в социальных сетях. Создавай короткие, информативные посты."

# Типы контента
CONTENT_TYPES = {
    "news": "Новостной",
    "edu": "Образовательный", 
    "fun": "Развлекательный",
    "anl": "Аналитический",
    "mot": "Мотивационный",
    "dis": "Дискуссионный",
    "rev": "Обзор",
    "list": "Список",
    "qa": "Вопрос-ответ",
    "story": "История"
}

# Тоны повествования
TONES = {
    "formal": "Официальный/формальный",
    "neutral": "Нейтральный",
    "friendly": "Дружелюбный/разговорный",
    "emotional": "Эмоциональный/восторженный",
    "humor": "Юмористический",
    "prof": "Профессиональный"
}

# Структурные элементы
STRUCTURE_OPTIONS = {
    "title": "Заголовок",
    "main": "Основной текст",
    "subheadings": "Подзаголовки",
    "quote": "Выделенная цитата",
    "conclusion": "Заключение/вывод",
    "hashtags": "Хэштеги",
    "emoji": "Эмодзи",
    "question": "Вовлекающий вопрос"
}

# Длина постов
LENGTH_OPTIONS = {
    "short": "Короткий (до 300 символов)",
    "medium": "Средний (300-800 символов)",
    "long": "Длинный (800-1500 символов)"
}

# Тематики блогов
BLOG_TOPICS = {
    "tech": "Технологии",
    "sport": "Спорт",
    "food": "Кулинария",
    "travel": "Путешествия",
    "fashion": "Мода",
    "health": "Здоровье", 
    "business": "Бизнес",
    "other": "Другое"
}

logger = logging.getLogger(__name__)

def validate_pro_prompt(prompt_text: str) -> bool:
    """
    Проверяет промпт режима PRO на соответствие правилам
    
    Args:
        prompt_text: Текст промпта
        
    Returns:
        bool: True если промпт допустим, иначе False
    """
    if len(prompt_text) > MAX_PROMPT_LENGTH:
        return False
        
    if any(keyword in prompt_text.lower() for keyword in FORBIDDEN_KEYWORDS):
        return False
        
    return True

def build_basic_prompt(params: dict) -> str:
    """
    Строит промпт из параметров конструктора BASIC
    
    Args:
        params: Словарь с параметрами конструктора
        
    Returns:
        str: Сформированный текст промпта
    """
    # Извлекаем параметры с подстановкой значений по умолчанию
    content_type = CONTENT_TYPES.get(params.get("content_type_code", "news"), "пост")
    theme = params.get("themes", "общая тема")
    tone_code = params.get("tone_code", "neutral")
    tone = TONES.get(tone_code, "нейтральный")
    blog_topic_code = params.get("blog_topic_code", "other")
    blog_topic = BLOG_TOPICS.get(blog_topic_code, "общая тематика")
    length_code = params.get("length_code", "medium")
    length = LENGTH_OPTIONS.get(length_code, "средний").split(" ")[0].lower()
    
    # Получаем структуру
    structure = params.get("structure", {"main": True})
    structure_elements = []
    
    if structure.get("title", False):
        structure_elements.append("заголовок")
    if structure.get("main", False):
        structure_elements.append("основной текст")
    if structure.get("subheadings", False):
        structure_elements.append("подзаголовки")
    if structure.get("quote", False):
        structure_elements.append("выделенную цитату")
    if structure.get("conclusion", False):
        structure_elements.append("заключение или вывод")
    if structure.get("hashtags", False):
        structure_elements.append("хэштеги")
    
    # Формируем базовый промпт
    prompt = f"Создай {content_type} на тему \"{theme}\" в сфере {blog_topic} в {tone} тоне. "
    
    if structure_elements:
        prompt += f"Пост должен включать: {', '.join(structure_elements)}. "
        
    prompt += f"Длина поста: {length}. "
    
    # Добавляем дополнительные опции
    if structure.get("emoji", False):
        prompt += "Используй подходящие эмодзи для украшения текста. "
        
    if structure.get("question", False):
        prompt += "Заверши пост вовлекающим вопросом для аудитории. "
    
    return prompt
