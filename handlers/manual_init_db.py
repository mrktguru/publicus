# manual_init_db.py
import asyncio
import os
import sqlite3

# Удалим существующий файл базы данных
DB_FILE = "bot.db"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print(f"Removed existing {DB_FILE}")

# Создаем новое соединение
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Создаем таблицы
print("Creating tables...")

# Таблица groups
cursor.execute('''
CREATE TABLE groups (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER UNIQUE,
    title TEXT,
    added_by INTEGER,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Таблица posts
cursor.execute('''
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    text TEXT,
    media_file_id TEXT,
    publish_at TIMESTAMP,
    created_by INTEGER,
    status TEXT DEFAULT 'approved',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published BOOLEAN DEFAULT 0
)
''')

# Таблица generated_series
cursor.execute('''
CREATE TABLE generated_series (
    id INTEGER PRIMARY KEY,
    prompt TEXT,
    repeat TEXT DEFAULT 'once',
    time TIMESTAMP,
    post_limit INTEGER DEFAULT 10,
    posts_generated INTEGER DEFAULT 0,
    moderation BOOLEAN DEFAULT 1
)
''')

conn.commit()
conn.close()

print("Database tables created successfully!")
print(f"Database file: {os.path.abspath(DB_FILE)}")
