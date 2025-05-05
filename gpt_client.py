import os
import openai
from config import OPENAI_API_KEY

# Устанавливаем API ключ
openai.api_key = OPENAI_API_KEY

async def generate_article(prompt: str) -> str:
    """
    Генерирует текст статьи по заданному промпту, используя актуальное API OpenAI
    """
    try:
        # Используем прямой вызов API без создания клиента
        completion = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты пишешь короткие новостные статьи на русском языке."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при генерации текста: {str(e)}")
        # Возвращаем сообщение об ошибке вместо того, чтобы прерывать выполнение
        return f"Не удалось сгенерировать контент: {str(e)}"


async def generate_example_post(prompt: str) -> str:
    """
    Генерирует пример поста для предпросмотра
    """
    try:
        # Используем прямой вызов API без создания клиента
        completion = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты создаешь примеры контента для социальных сетей."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при генерации примера поста: {str(e)}")
        # Возвращаем сообщение об ошибке вместо того, чтобы прерывать выполнение
        return f"Не удалось сгенерировать пример: {str(e)}"
