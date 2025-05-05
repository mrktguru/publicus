import openai
from config import OPENAI_API_KEY
from openai import OpenAI

# Создаем клиента OpenAI с минимальными необходимыми параметрами
client = OpenAI(
    api_key=OPENAI_API_KEY
    # Убираем параметр proxies, который вызывает ошибку
)

async def generate_article(prompt: str) -> str:
    """
    Генерирует текст статьи по заданному промпту, используя актуальное API OpenAI
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты пишешь короткие новостные статьи на русском языке."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        # Добавляем обработку ошибок
        print(f"Ошибка при генерации текста: {str(e)}")
        raise e


async def generate_example_post(prompt: str) -> str:
    """
    Генерирует пример поста для предпросмотра
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты создаешь примеры контента для социальных сетей."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        # Добавляем обработку ошибок
        print(f"Ошибка при генерации примера поста: {str(e)}")
        raise e
