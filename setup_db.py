#!/usr/bin/env python3
# setup_db.py
import sqlite3
import os

DB_FILE = "bot.db"

# Удаляем существующую базу данных, если она есть
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print(f"Существующая база данных {DB_FILE} удалена")

# Создаем новую базу данных
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Создаем таблицу users
cursor.execute('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE,
    username TEXT,
    full_name TEXT,
    email TEXT,
    role TEXT DEFAULT 'account_owner',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    current_chat_id INTEGER,
    settings_json TEXT
)
''')

# Создаем таблицу groups
cursor.execute('''
CREATE TABLE groups (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER UNIQUE,
    title TEXT,
    username TEXT,
    display_name TEXT,
    type TEXT DEFAULT 'channel',
    added_by INTEGER,
    is_active INTEGER DEFAULT 1,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_post_at TIMESTAMP
)
''')

# Создаем таблицу group_settings
cursor.execute('''
CREATE TABLE group_settings (
    id INTEGER PRIMARY KEY,
    group_id INTEGER,
    spreadsheet_id TEXT,
    spreadsheet_name TEXT,
    default_signature TEXT,
    auto_hashtags TEXT,
    posting_timezone TEXT DEFAULT 'Europe/Moscow',
    additional_settings TEXT
)
''')

# Создаем таблицу posts
cursor.execute('''
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    text TEXT,
    media_file_id TEXT,
    media_type TEXT,
    publish_at TIMESTAMP,
    created_by INTEGER,
    status TEXT DEFAULT 'approved',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published INTEGER DEFAULT 0,
    is_generated INTEGER DEFAULT 0,
    template_id INTEGER,
    generation_params TEXT,
    rejection_reason TEXT
)
''')

# Создаем таблицу generated_series
cursor.execute('''
CREATE TABLE generated_series (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    prompt TEXT,
    repeat TEXT DEFAULT 'once',
    time TIMESTAMP,
    post_limit INTEGER DEFAULT 10,
    posts_generated INTEGER DEFAULT 0,
    moderation INTEGER DEFAULT 1
)
''')

# Создаем таблицу generation_templates
cursor.execute('''
CREATE TABLE generation_templates (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    chat_id INTEGER,
    content_type TEXT,
    themes TEXT,
    tone TEXT,
    structure TEXT,
    length TEXT,
    post_count INTEGER DEFAULT 1,
    moderation_enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
)
''')

# Создаем таблицу google_sheets
cursor.execute('''
CREATE TABLE google_sheets (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    spreadsheet_id TEXT,
    sheet_name TEXT DEFAULT 'Контент-план',
    last_sync TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_interval INTEGER DEFAULT 15,
    settings TEXT
)
''')

# Добавляем администратора по умолчанию (при необходимости)
try:
    import os
    default_admin_id = os.getenv("DEFAULT_ADMIN_ID")
    if default_admin_id:
        cursor.execute('''
        INSERT INTO users (user_id, role, is_active)
        VALUES (?, 'admin', 1)
        ''', (int(default_admin_id),))
        print(f"Добавлен администратор с ID {default_admin_id}")
except Exception as e:
    print(f"Ошибка при добавлении администратора: {e}")

# Сохраняем изменения и закрываем соединение
conn.commit()
conn.close()
print(f"База данных {DB_FILE} успешно создана со всеми необходимыми таблицами!")
