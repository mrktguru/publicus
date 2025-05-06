# gpt_client.py с оптимизированным использованием контекста для разных режимов
import requests
import json
from config import OPENAI_API_KEY
from utils.prompt_manager import SYSTEM_CONTEXT

async def generate_article(prompt: str) -> str:
    """
    Генерирует текст статьи по заданному промпту через прямой HTTP запрос к API OpenAI
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "Ты пишешь короткие посты для социальных сетей на русском языке. Не используй явные маркеры структуры текста вроде 'Основной текст:', 'Подзаголовок:', 'Заключение:' и т.п. Форматируй текст органично и естественно."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            print(f"Ошибка API: {response.status_code}, {response.text}")
            return f"Не удалось сгенерировать контент: Ошибка API {response.status_code}"
    
    except Exception as e:
        print(f"Ошибка при генерации текста: {str(e)}")
        return f"Не удалось сгенерировать контент: {str(e)}"


async def generate_example_post(prompt: str) -> str:
    """
    Генерирует пример поста для предпросмотра через прямой HTTP запрос к API OpenAI
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "Ты создаешь примеры контента для социальных сетей."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            print(f"Ошибка API: {response.status_code}, {response.text}")
            return f"Не удалось сгенерировать пример: Ошибка API {response.status_code}"
    
    except Exception as e:
        print(f"Ошибка при генерации примера поста: {str(e)}")
        return f"Не удалось сгенерировать пример: {str(e)}"
