import sqlite3

# Создаем подключение
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

# Удаляем существующие таблицы, если они есть
cursor.execute("DROP TABLE IF EXISTS groups")
cursor.execute("DROP TABLE IF EXISTS posts")
cursor.execute("DROP TABLE IF EXISTS generated_series")

# Создаем таблицу groups с полем added_by
cursor.execute('''
CREATE TABLE groups (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER UNIQUE,
    title TEXT,
    added_by INTEGER,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Создаем таблицу posts
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

# Создаем таблицу generated_series
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

# Сохраняем изменения
conn.commit()
conn.close()
print("База данных успешно создана!")
