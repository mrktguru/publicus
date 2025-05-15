# utils/google_sheets.py
import os
import json
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from config import GOOGLE_CREDS_FILE, GOOGLE_SERVICE_ACCOUNT_EMAIL

# Настройка логирования
logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """Клиент для работы с Google Sheets API"""
    
    # Добавляем константу с email сервисного аккаунта из конфига
    SERVICE_ACCOUNT = GOOGLE_SERVICE_ACCOUNT_EMAIL
    
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
            # Если range_name содержит кириллицу, кодируем его правильно
            if "!" in range_name:
                sheet_name, cell_range = range_name.split("!")
                # Пробуем использовать имя листа по индексу вместо по названию
                # Сначала получим список всех листов
                metadata = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
                sheets = metadata.get('sheets', [])
                sheet_found = False
                
                # Ищем лист по названию
                for sheet in sheets:
                    if sheet['properties']['title'] == sheet_name:
                        # Если нашли, используем кавычки для названия листа
                        range_name = f"'{sheet_name}'!{cell_range}"
                        sheet_found = True
                        break
                
                if not sheet_found:
                    # Если лист не найден, пробуем первый лист
                    logger.warning(f"Sheet '{sheet_name}' not found, using first sheet instead")
                    if sheets:
                        first_sheet_name = sheets[0]['properties']['title']
                        range_name = f"'{first_sheet_name}'!{cell_range}"
                    else:
                        raise Exception(f"No sheets found in spreadsheet {spreadsheet_id}")
            
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
            # Если range_name содержит кириллицу, форматируем корректно
            if "!" in range_name:
                sheet_name, cell_range = range_name.split("!")
                range_name = f"'{sheet_name}'!{cell_range}"
                
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
    
    def create_sheet_structure(self, spreadsheet_id, chat_id=None, chat_title=None):
        """
        Создает необходимую структуру в таблице: листы и заголовки столбцов.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            chat_id: ID канала/группы
            chat_title: Название канала/группы
            
        Returns:
            bool: Успешно ли создана структура
        """
        try:
            logger.info(f"Creating structure for spreadsheet {spreadsheet_id}")
            
            # 1. Проверяем, существуют ли уже нужные листы
            metadata = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = metadata.get('sheets', [])
            sheet_titles = [sheet['properties']['title'] for sheet in sheets]
            
            # Список листов, которые нужно создать
            required_sheets = ['Контент-план', 'История']
            sheets_to_create = [sheet for sheet in required_sheets if sheet not in sheet_titles]
            
            # 2. Создаем недостающие листы
            if sheets_to_create:
                requests = []
                for sheet_title in sheets_to_create:
                    requests.append({
                        'addSheet': {
                            'properties': {
                                'title': sheet_title
                            }
                        }
                    })
                
                # Отправляем запрос на создание листов
                result = self.service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info(f"Created sheets: {sheets_to_create}")
                
                # Получаем обновленные метаданные после создания листов
                metadata = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            
            # 3. Добавляем заголовки в Контент-план
            content_plan_headers = [
                ['ID', 'Канал/Группа', 'Дата публикации', 'Время публикации', 
                'Заголовок', 'Текст', 'Медиа', 'Статус', 'Комментарии']
            ]
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="'Контент-план'!A1:I1",
                valueInputOption='RAW',
                body={'values': content_plan_headers}
            ).execute()
            
            # 4. Добавляем заголовки в Историю
            history_headers = [
                ['ID', 'Канал/Группа', 'Дата публикации', 'Время публикации', 
                'Текст', 'Результат', 'Комментарии']
            ]
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="'История'!A1:G1",
                valueInputOption='RAW',
                body={'values': history_headers}
            ).execute()
            
            # 5. Получаем ID листа Контент-план
            content_plan_sheet_id = self._get_sheet_id_by_name(metadata, 'Контент-план')
            history_sheet_id = self._get_sheet_id_by_name(metadata, 'История')
            
            # 6. Формируем список запросов для форматирования
            requests = []
            
            # 7. Добавляем выпадающий список для статуса
            if content_plan_sheet_id is not None:
                # Выпадающий список для статуса
                status_values = ['Ожидает', 'Опубликован', 'Отложен', 'Отменен']
                
                requests.append({
                    'setDataValidation': {
                        'range': {
                            'sheetId': content_plan_sheet_id,
                            'startRowIndex': 1,     # Со второй строки
                            'endRowIndex': 1000,    # До 1000-й строки
                            'startColumnIndex': 7,  # Столбец H (индексация с 0)
                            'endColumnIndex': 8     # До столбца H
                        },
                        'rule': {
                            'condition': {
                                'type': 'ONE_OF_LIST',
                                'values': [{'userEnteredValue': status} for status in status_values]
                            },
                            'strict': True,
                            'showCustomUi': True
                        }
                    }
                })
                
                # Добавляем форматирование заголовков
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': content_plan_sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {
                                    'bold': True
                                },
                                'backgroundColor': {
                                    'red': 0.9,
                                    'green': 0.9,
                                    'blue': 0.9
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                    }
                })
            
            if history_sheet_id is not None:
                # Форматирование для листа История
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': history_sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {
                                    'bold': True
                                },
                                'backgroundColor': {
                                    'red': 0.9,
                                    'green': 0.9,
                                    'blue': 0.9
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                    }
                })
            
            # 8. Если предоставлены данные о канале, предзаполняем значения столбца Канал/Группа
            if chat_id and chat_title and content_plan_sheet_id is not None:
                # Предзаполняем значения для 50 строк
                channel_values = [[f"{chat_title} ({chat_id})"] for _ in range(50)]
                self.service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range="'Контент-план'!B2:B51",
                    valueInputOption='RAW',
                    body={'values': channel_values}
                ).execute()
                
                # Защита столбца с данными канала
                requests.append({
                    'addProtectedRange': {
                        'protectedRange': {
                            'range': {
                                'sheetId': content_plan_sheet_id,
                                'startRowIndex': 1,     # Со второй строки
                                'endRowIndex': 1000,    # До 1000-й строки
                                'startColumnIndex': 1,  # Столбец B (индексация с 0)
                                'endColumnIndex': 2     # До столбца B
                            },
                            'description': 'Защита значения канала/группы',
                            'warningOnly': True  # Только предупреждение при попытке изменения
                        }
                    }
                })
            
            # 9. Автоматическая ширина столбцов
            for sheet_name in required_sheets:
                sheet_id = self._get_sheet_id_by_name(metadata, sheet_name)
                if sheet_id is not None:
                    requests.append({
                        'autoResizeDimensions': {
                            'dimensions': {
                                'sheetId': sheet_id,
                                'dimension': 'COLUMNS',
                                'startIndex': 0,
                                'endIndex': 9  # Количество столбцов
                            }
                        }
                    })
            
            # 10. Применяем все запросы форматирования
            if requests:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'requests': requests}
                ).execute()
            
            logger.info("Sheet structure created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating sheet structure: {e}")
            return False




    
    def update_post_status(self, spreadsheet_id, sheet_name, row_index, status):
        """
        Обновление статуса поста в таблице.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            sheet_name: Имя листа
            row_index: Номер строки
            status: Новый статус
        """
        range_name = f"'{sheet_name}'!H{row_index}"
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
        history_range = "'История'!A:F"
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
        range_name = f"'{sheet_name}'!A2:I"
        
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

    def update_cell_value(self, spreadsheet_id, sheet_name, row, col, value):
        """
        Обновляет значение конкретной ячейки в таблице.
        
        Args:
            spreadsheet_id: ID Google Таблицы
            sheet_name: Имя листа
            row: Номер строки (начиная с 1)
            col: Буква столбца (A, B, C, ...)
            value: Новое значение
        """
        try:
            range_name = f"'{sheet_name}'!{col}{row}"
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
            logger.error(f"Error updating cell {col}{row} in sheet {sheet_name}: {e}")
            raise
