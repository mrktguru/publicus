# utils/google_sheets.py
import os
import json
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from config import GOOGLE_CREDS_FILE

# Настройка логирования
logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """Клиент для работы с Google Sheets API"""
    
    def __init__(self, credentials_file=None):
        """
        Инициализация клиента Google Sheets API.
        
        Args:
            credentials_file: Путь к файлу с учетными данными сервисного аккаунта.
                             По умолчанию берется из настроек.
        """
        self.credentials_file = credentials_file or GOOGLE_CREDS_FILE
        self._service = None
        
        # Проверяем наличие файла с учетными данными
        if not os.path.exists(self.credentials_file):
            logger.warning(f"Файл учетных данных Google API не найден: {self.credentials_file}")
    
    @property
    def service(self):
        """Получение сервиса Google Sheets API с ленивой инициализацией."""
        if not self._service:
            try:
                # Используем учетные данные сервисного аккаунта
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file, 
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                self._service = build('sheets', 'v4', credentials=credentials)
                logger.info("Google Sheets API service initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing Google Sheets API service: {e}")
                raise
        return self._service
    
    def get_sheet_data(self, spreadsheet_id, range_name):
        """
        Получение данных из указанного диапазона таблицы.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            range_name: Диапазон ячеек (например, "Sheet1!A1:D10")
            
        Returns:
            list: Список строк с данными
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            return result.get('values', [])
        except Exception as e:
            logger.error(f"Error getting data from sheet {spreadsheet_id}, range {range_name}: {e}")
            raise
    
    def update_cell(self, spreadsheet_id, range_name, value):
        """
        Обновление значения в указанной ячейке.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            range_name: Диапазон ячеек (например, "Sheet1!A1")
            value: Новое значение
            
        Returns:
            dict: Результат операции
        """
        try:
            body = {
                'values': [[value]]
            }
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            return result
        except Exception as e:
            logger.error(f"Error updating cell in sheet {spreadsheet_id}, range {range_name}: {e}")
            raise
    
    def get_upcoming_posts(self, spreadsheet_id, sheet_name="Контент-план"):
        """
        Получение постов, запланированных к публикации в ближайшее время.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            sheet_name: Имя листа (по умолчанию "Контент-план")
            
        Returns:
            list: Список словарей с данными о постах
        """
        logger.info(f"Looking for upcoming posts in sheet {spreadsheet_id}, sheet {sheet_name}")
        
        # Формируем диапазон для запроса всех данных листа (начиная со второй строки)
        range_name = f"{sheet_name}!A2:I"
        
        try:
            data = self.get_sheet_data(spreadsheet_id, range_name)
            logger.info(f"Found {len(data)} rows in content plan")
            
            upcoming_posts = []
            now = datetime.now()
            check_interval = now + timedelta(minutes=30)  # Проверяем посты на ближайшие 30 минут
            
            # Обработка полученных данных
            for row_index, row in enumerate(data, start=2):  # Начинаем с индекса 2, т.к. первая строка - заголовки
                # Проверяем, что у нас достаточно данных в строке
                if len(row) < 8:
                    logger.warning(f"Row {row_index} has insufficient data: {row}")
                    continue
                    
                try:
                    # Извлекаем данные из строки
                    post_id = row[0]
                    channel = row[1]
                    date_str = row[2]
                    time_str = row[3]
                    status = row[7] if len(row) > 7 else ""
                    
                    # Проверяем статус
                    if status.lower() != "ожидает":
                        logger.debug(f"Skipping row {row_index}, status is not 'ожидает': {status}")
                        continue
                        
                    # Парсим дату и время
                    try:
                        date_parts = date_str.split('.')
                        if len(date_parts) != 3:
                            logger.warning(f"Invalid date format in row {row_index}: {date_str}")
                            continue
                            
                        day, month, year = map(int, date_parts)
                        
                        time_parts = time_str.split(':')
                        if len(time_parts) != 2:
                            logger.warning(f"Invalid time format in row {row_index}: {time_str}")
                            continue
                            
                        hour, minute = map(int, time_parts)
                        
                        # Формируем дату и время публикации
                        publish_datetime = datetime(year, month, day, hour, minute)
                    except Exception as e:
                        logger.warning(f"Error parsing datetime in row {row_index}: {e}")
                        continue
                    
                    # Проверяем, находится ли время публикации в интервале проверки
                    if now <= publish_datetime <= check_interval:
                        post_data = {
                            'id': post_id,
                            'channel': channel,
                            'publish_datetime': publish_datetime,
                            'title': row[4] if len(row) > 4 else "",
                            'text': row[5] if len(row) > 5 else "",
                            'media': row[6] if len(row) > 6 else "",
                            'row_index': row_index  # Индекс строки в таблице для обновления
                        }
                        upcoming_posts.append(post_data)
                        logger.info(f"Found upcoming post at {publish_datetime}: {post_id}")
                except Exception as e:
                    logger.error(f"Error processing row {row_index}: {e}")
                    continue
                    
            return upcoming_posts
        
        except Exception as e:
            logger.error(f"Error getting upcoming posts: {e}")
            return []
    
    def update_post_status(self, spreadsheet_id, sheet_name, row_index, status):
        """
        Обновление статуса поста в таблице.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            sheet_name: Имя листа
            row_index: Номер строки
            status: Новый статус
        """
        range_name = f"{sheet_name}!H{row_index}"
        try:
            result = self.update_cell(spreadsheet_id, range_name, status)
            logger.info(f"Updated status for row {row_index} to '{status}'")
            return result
        except Exception as e:
            logger.error(f"Error updating post status: {e}")
            return None
        
    def add_to_history(self, spreadsheet_id, post_data, publish_result):
        """
        Добавление информации о публикации в лист История.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            post_data: Данные о посте
            publish_result: Результат публикации
        """
        history_range = "История!A:F"
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        try:
            # Данные для добавления в историю
            history_row = [
                post_data['id'],              # ID поста
                post_data['channel'],         # Канал/группа
                now,                          # Время фактической публикации
                post_data['text'][:100] + "..." if len(post_data['text']) > 100 else post_data['text'],  # Сокращенный текст
                publish_result,               # Результат публикации
                "Опубликовано автоматически"  # Комментарий
            ]
            
            body = {
                'values': [history_row]
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=history_range,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Added entry to history for post {post_data['id']}")
            return result
            
        except Exception as e:
            logger.error(f"Error adding to history: {e}")
            return None
