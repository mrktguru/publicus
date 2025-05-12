import sqlite3
import sys

# Путь к файлу базы данных
DB_FILE = "bot.db"

def fix_channel_tables(channel_title=None):
    """Исправляет таблицы для конкретного канала"""
    if not channel_title:
        print("Укажите название канала в кавычках, например: python fix_channel.py \"Ногомяч: все о футболе!\"")
        return
    
    # Подключаемся к базе данных
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Находим канал по названию
    cursor.execute("SELECT chat_id, title FROM groups WHERE title LIKE ?", (f"%{channel_title}%",))
    channels = cursor.fetchall()
    
    if not channels:
        print(f"Каналы с названием '{channel_title}' не найдены")
        cursor.execute("SELECT chat_id, title FROM groups LIMIT 10")
        existing = cursor.fetchall()
        print("Доступные каналы:")
        for chat_id, title in existing:
            print(f"- {title} (ID: {chat_id})")
        conn.close()
        return
    
    for chat_id, title in channels:
        print(f"Найден канал: {title} (ID: {chat_id})")
        
        # Проверяем активные таблицы для этого канала
        cursor.execute("SELECT id, spreadsheet_id FROM google_sheets WHERE chat_id = ? AND is_active = 1", (chat_id,))
        active_sheets = cursor.fetchall()
        
        if active_sheets:
            print(f"Найдено активных таблиц: {len(active_sheets)}")
            for sheet_id, sheet_name in active_sheets:
                print(f"- Таблица ID: {sheet_id}, Name: {sheet_name}")
            
            # Деактивируем все таблицы для этого канала
            cursor.execute("UPDATE google_sheets SET is_active = 0 WHERE chat_id = ?", (chat_id,))
            conn.commit()
            print(f"Все таблицы для канала {title} деактивированы")
        else:
            print(f"Для канала {title} нет активных таблиц")
    
    # Закрываем соединение
    conn.close()
    print("Операция завершена. Перезапустите бота.")

if __name__ == "__main__":
    channel_name = sys.argv[1] if len(sys.argv) > 1 else None
    fix_channel_tables(channel_name)
