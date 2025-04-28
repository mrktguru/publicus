import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

async def generate_article(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Ты пишешь короткие новостные статьи на русском языке."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    return response.choices[0].message.content