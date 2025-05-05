FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копирование файлов
COPY . /app/

# Делаем entrypoint исполняемым
RUN chmod +x /app/docker-entrypoint.sh

# Запускаем через entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# В вашем Dockerfile
RUN pip install requests
