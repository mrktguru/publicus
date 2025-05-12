import sqlite3
import json

# Путь к файлу базы данных
DB_FILE = "bot.db"

def fix_sheets_problem():
    """Функция для исправления проблемы с таблицами в базе данных"""
    # Подключаемся к базе данных
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Посчитаем количество активных таблиц
    cursor.execute("SELECT COUNT(*) FROM google_sheets WHERE is_active = 1")
    active_count = cursor.fetchone()[0]
    
    print(f"Всего активных таблиц в БД: {active_count}")
    
    # Получаем информацию по каналам
    cursor.execute("""
        SELECT g.chat_id, g.title, COUNT(gs.id) 
        FROM groups g 
        LEFT JOIN google_sheets gs ON g.chat_id = gs.chat_id AND gs.is_active = 1
        GROUP BY g.chat_id
    """)
    channel_stats = cursor.fetchall()
    
    print("\nСтатистика по каналам:")
    for chat_id, title, sheets_count in channel_stats:
        print(f"Канал '{title}' (ID: {chat_id}): активных таблиц - {sheets_count}")
    
    # Ставим все таблицы в неактивное состояние
    cursor.execute("UPDATE google_sheets SET is_active = 0")
    conn.commit()
    
    print("\nВсе таблицы помечены как неактивные")
    
    # Проверяем, что изменения применились
    cursor.execute("SELECT COUNT(*) FROM google_sheets WHERE is_active = 1")
    new_active_count = cursor.fetchone()[0]
    
    print(f"Активных таблиц после обновления: {new_active_count}")
    
    # Закрываем соединение
    conn.close()

if __name__ == "__main__":
    fix_sheets_problem()
    print("Скрипт выполнен. Перезапустите бота.")
