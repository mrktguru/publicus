#!/bin/bash
set -e

# Инициализация базы данных
echo "Initializing database..."
python init_db.py

# Запуск бота
echo "Starting bot..."
exec python bot.py
