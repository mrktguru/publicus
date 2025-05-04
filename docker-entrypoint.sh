#!/bin/bash
set -e

# Инициализация базы данных
echo "Checking if database exists..."
if [ ! -s /app/bot.db ]; then
    echo "Database file empty or not found, initializing..."
    python manual_init_db.py
    echo "Database initialized successfully!"
else
    echo "Database already exists, skipping initialization"
fi

# Запуск бота
echo "Starting bot..."
exec python bot.py
