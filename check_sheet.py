#!/usr/bin/env python3
import sqlite3
import os

# Путь к файлу базы данных
DB_FILE = "bot.db"

def check_sheets_status():
    """Проверяет состояние подключений таблиц"""
    if not os.path.exists(DB_FILE):
        print(f"[ОШИБКА] Файл базы данных {DB_FILE} не найден!")
        return False
    
    try:
        # Подключаемся к базе
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Получаем количество записей
        cursor.execute("SELECT COUNT(*) FROM google_sheets")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM google_sheets WHERE is_active = 1")
        active_count = cursor.fetchone()[0]
        
        print(f"[i] Всего записей в таблице google_sheets: {total_count}")
        print(f"[i] Активных записей: {active_count}")
        
        # Получаем каналы с активными таблицами
        cursor.execute("""
            SELECT g.chat_id, g.title, COUNT(gs.id) 
            FROM groups g 
            JOIN google_sheets gs ON g.chat_id = gs.chat_id AND gs.is_active = 1
            GROUP BY g.chat_id
        """)
        active_channels = cursor.fetchall()
        
        if active_channels:
            print(f"\n[i] Найдены каналы с активными таблицами ({len(active_channels)}):")
            for chat_id, title, count in active_channels:
                print(f"    - {title} (ID: {chat_id}): {count} активных таблиц")
                
                # Выводим подробности по таблицам этого канала
                cursor.execute("""
                    SELECT id, spreadsheet_id, sheet_name
                    FROM google_sheets 
                    WHERE chat_id = ? AND is_active = 1
                """, (chat_id,))
                sheets = cursor.fetchall()
                
                for sheet_id, spreadsheet_id, sheet_name in sheets:
                    print(f"      * ID: {sheet_id}, Sheet ID: {spreadsheet_id}, Name: {sheet_name}")
        else:
            print("[i] Не найдены каналы с активными таблицами")
            
        # Закрываем соединение
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ОШИБКА] {str(e)}")
        return False

if __name__ == "__main__":
    print("=== ПРОВЕРКА СОСТОЯНИЯ ПОДКЛЮЧЕНИЙ ТАБЛИЦ ===")
    check_sheets_status()
