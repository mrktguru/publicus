FROM python:3.11-slim

WORKDIR /app

# Установим зависимости для сборки некоторых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# По умолчанию запускаем бота, но это может быть переопределено в docker-compose.yml
CMD ["python", "bot.py"]
