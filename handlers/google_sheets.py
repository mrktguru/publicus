import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import User, GoogleSheet
from utils.google_sheets import GoogleSheetsClient

router = Router()
logger = logging.getLogger(__name__)

class GoogleSheetStates(StatesGroup):
    """Состояния для процесса добавления Google Таблицы"""
    waiting_for_url = State()
    waiting_for_sheet_name = State()
    waiting_for_interval = State()

@router.message(lambda m: m.text == "Таблицы")
async def sheets_menu(message: Message, state: FSMContext):
    """Обработчик для меню Google Таблиц."""
    logger.info("Entering sheets_menu function")
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await message.answer(
                    "⚠️ Сначала выберите канал или группу для работы.\n"
                    "Используйте кнопку 'Сменить группу' в главном меню."
                )
                return
            
            channel_id = user.current_chat_id
            
            # ПРИНЦИПИАЛЬНО НОВЫЙ ПОДХОД: 
            # Сначала создаем базовое сообщение без клавиатуры
            base_message = "📊 <b>Google Таблицы</b>\n\n"
            
            # Получаем все АКТИВНЫЕ таблицы для данного канала
            sheets_q = select(GoogleSheet).filter(
                GoogleSheet.chat_id == channel_id,
                GoogleSheet.is_active == True
            )
            sheets_result = await session.execute(sheets_q)
            active_sheets = sheets_result.scalars().all()
            
            # Явно считаем количество таблиц
            sheet_count = len(active_sheets)
            
            # ЛОГИРОВАНИЕ для отладки
            logger.info(f"Channel ID: {channel_id}, active sheets count: {sheet_count}")
            
            # Формируем разные клавиатуры в зависимости от наличия таблиц
            if sheet_count > 0:
                # Есть активные таблицы
                sheets_text = "\n".join([
                    f"{i+1}. Таблица {sheet.spreadsheet_id[:15]}... "
                    f"(лист: {sheet.sheet_name}, "
                    f"последняя синхронизация: {sheet.last_sync.strftime('%d.%m.%Y %H:%M') if sheet.last_sync else 'никогда'})"
                    for i, sheet in enumerate(active_sheets)
                ])
                
                # Комбинируем сообщение
                full_message = base_message + sheets_text + "\n\n" + \
                              "Для управления таблицами используйте кнопки ниже."
                
                # Клавиатура С кнопкой синхронизации
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="🗑 Удалить таблицу", 
                            callback_data=f"delete_sheet:{active_sheets[0].id}"
                        ),
                        InlineKeyboardButton(
                            text="🔄 Синхронизировать", 
                            callback_data="sync_sheets_now"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="➕ Подключить новую таблицу", 
                            callback_data="sheet_connect"
                        )
                    ]
                ]
                
                logger.info("Created keyboard WITH sync button - sheets found")
                
            else:
                # Нет активных таблиц
                full_message = base_message + "У этого канала пока нет подключенных таблиц.\n\n" + \
                              "Чтобы подключить таблицу, нажмите кнопку ниже или используйте команду /addsheet.\n\n" + \
                              "<i>Для работы с таблицами вам необходимо:</i>\n" + \
                              "1. Создать таблицу в Google Sheets\n" + \
                              "2. Настроить доступ для сервисного аккаунта бота\n" + \
                              "3. Скопировать URL таблицы"
                
                # Клавиатура БЕЗ кнопки синхронизации
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="➕ Подключить таблицу", 
                            callback_data="sheet_connect"
                        )
                    ]
                ]
                
                logger.info("Created keyboard WITHOUT sync button - no sheets found")
            
            # Отправка сообщения с подготовленной клавиатурой
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer(full_message, parse_mode="HTML", reply_markup=markup)
            
    except Exception as e:
        logger.error(f"Error showing sheets menu: {e}")
        await message.answer("⚠️ Произошла ошибка при получении данных о таблицах. Пожалуйста, попробуйте позже.")

# Добавляем новый обработчик для кнопки удаления таблицы
@router.callback_query(lambda c: c.data.startswith("delete_sheet:"))
async def delete_sheet_callback(call: CallbackQuery):
    """Обработчик для удаления таблицы через коллбэк"""
    try:
        # Извлекаем ID таблицы из callback_data
        sheet_id = int(call.data.split(":")[1])
        
        async with AsyncSessionLocal() as session:
            # Находим таблицу по ID
            sheet = await session.get(GoogleSheet, sheet_id)
            
            if not sheet:
                await call.answer("⚠️ Таблица не найдена", show_alert=True)
                return
            
            chat_id = sheet.chat_id  # Сохраняем chat_id перед удалением
            
            # Проверяем права пользователя на удаление (владелец или админ)
            user_id = call.from_user.id
            if sheet.created_by != user_id:
                # Проверяем, является ли пользователь админом
                user_q = select(User).filter(User.user_id == user_id)
                user_result = await session.execute(user_q)
                user = user_result.scalar_one_or_none()
                
                if not user or user.role != "admin":
                    await call.answer("⚠️ У вас нет прав на удаление этой таблицы", show_alert=True)
                    return
            
            # Помечаем таблицу как неактивную (мягкое удаление)
            sheet.is_active = False
            await session.commit()
            
            # Отправляем сообщение об успешном удалении
            await call.answer("✅ Таблица успешно отключена", show_alert=False)
            
            # ВАЖНОЕ ИЗМЕНЕНИЕ: Проверяем остались ли активные таблицы после удаления
            sheets_q = select(GoogleSheet).filter(
                GoogleSheet.chat_id == chat_id,
                GoogleSheet.is_active == True
            )
            sheets_result = await session.execute(sheets_q)
            active_sheets = sheets_result.scalars().all()
            active_count = len(active_sheets)
            
            logger.info(f"After deletion: {active_count} active sheets remain for channel {chat_id}")
            
            if active_count > 0:
                # Если остались другие активные таблицы, показываем их с кнопками
                sheets_text = "\n".join([
                    f"{i+1}. Таблица {s.spreadsheet_id[:15]}... "
                    f"(лист: {s.sheet_name}, "
                    f"последняя синхронизация: {s.last_sync.strftime('%d.%m.%Y %H:%M') if s.last_sync else 'никогда'})"
                    for i, s in enumerate(active_sheets)
                ])
                
                # Берем первую из оставшихся таблиц
                first_sheet = active_sheets[0]
                
                # Обновляем сообщение, показывая оставшиеся таблицы с кнопками управления
                await call.message.edit_text(
                    f"📊 <b>Подключенные Google Таблицы</b>\n\n"
                    f"{sheets_text}\n\n"
                    f"Таблица успешно отключена, остальные таблицы доступны.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🗑 Удалить таблицу", callback_data=f"delete_sheet:{first_sheet.id}"),
                            InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")
                        ],
                        [InlineKeyboardButton(text="➕ Подключить новую таблицу", callback_data="sheet_connect")]
                    ])
                )
            else:
                # Если не осталось активных таблиц, показываем сообщение без кнопки синхронизации
                await call.message.edit_text(
                    "📊 <b>Google Таблицы</b>\n\n"
                    "Таблица успешно отключена. У канала больше нет подключенных таблиц.\n\n"
                    "Чтобы подключить таблицу, нажмите кнопку ниже или используйте команду /addsheet.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")]
                    ])
                )
                
    except Exception as e:
        logger.error(f"Error deleting sheet: {e}")
        await call.answer("⚠️ Произошла ошибка при удалении таблицы", show_alert=True)


# Обработчики для коллбэков, связанных только с Google Sheets
@router.callback_query(lambda c: c.data in ["sheet_connect", "add_sheet"])
async def sheets_add_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик для коллбэков добавления таблицы."""
    logger.info(f"Sheet add callback received: {call.data}")
    await handle_add_sheet_callback(call, state)

@router.callback_query(F.data == "sync_sheets_now")
async def sync_sheets_now_callback(call: CallbackQuery):
    """Обработчик для коллбэка синхронизации таблиц."""
    logger.info(f"Sync sheets callback received: {call.data}")
    
    # Код обработки синхронизации
    user_id = call.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await call.answer("⚠️ Сначала выберите канал или группу", show_alert=True)
                return
            
            channel_id = user.current_chat_id
            
            # Получаем информацию о подключенных таблицах для этого канала
            sheets_q = select(GoogleSheet).filter(GoogleSheet.chat_id == channel_id, GoogleSheet.is_active == True)
            sheets_result = await session.execute(sheets_q)
            sheets = sheets_result.scalars().all()
            
            if not sheets:
                await call.answer("⚠️ У выбранного канала нет активных подключений к Google Таблицам", show_alert=True)
                return
            
            # Сообщаем о начале синхронизации
            await call.answer("🔄 Начинаю синхронизацию...", show_alert=False)
            status_message = await call.message.answer("🔄 Начинаю синхронизацию таблиц...")
            
            # Запускаем синхронизацию каждой таблицы
            from scheduler import check_google_sheets
            
            # Запускаем проверку таблиц
            await check_google_sheets(call.bot)
            
            # Сообщаем о завершении синхронизации
            await status_message.edit_text("✅ Синхронизация завершена успешно!")
            
    except Exception as e:
        logger.error(f"Error syncing sheets: {e}")
        await call.answer("❌ Ошибка при синхронизации", show_alert=True)
        await call.message.answer(f"❌ Ошибка при синхронизации таблиц: {str(e)}")

async def handle_add_sheet_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик callback для добавления таблицы"""
    logger.info("Processing add_sheet/sheet_connect callback")
    
    user_id = call.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await call.answer("⚠️ Сначала выберите канал или группу", show_alert=True)
                return
            
            # Сохраняем канал в состоянии
            await state.update_data(sheet_channel_id=user.current_chat_id)
            
            instructions_text = (
                "📊 <b>Подключение Google Таблицы</b>\n\n"
                "Для подключения таблицы выполните следующие шаги:\n\n"
                "1. Создайте <b>пустую</b> таблицу в Google Sheets\n"
                "2. Откройте доступ для редактирования следующему email:\n"
                f"<code>{GoogleSheetsClient.SERVICE_ACCOUNT}</code>\n\n"
                "3. Отправьте URL таблицы в формате:\n"
                "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit\n\n"
                "<i>Бот автоматически создаст необходимую структуру: листы 'Контент-план' и 'История' "
                "с нужными заголовками столбцов.</i>"
            )
            
            # Отправляем ответ на коллбэк
            await call.answer()
            
            # Отправляем новое сообщение с инструкциями
            await call.message.answer(
                text=instructions_text,
                parse_mode="HTML"
            )
            
            # Устанавливаем состояние ожидания URL
            await state.set_state(GoogleSheetStates.waiting_for_url)
            
    except Exception as e:
        logger.error(f"Error in handle_add_sheet_callback: {e}")
        await call.answer("⚠️ Произошла ошибка при начале процесса добавления таблицы", show_alert=True)

@router.message(Command('addsheet'))
async def add_sheet_command(message: Message, state: FSMContext):
    """Начало процесса добавления новой таблицы через команду."""
    logger.info("Received addsheet command")
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await message.answer(
                    "⚠️ Сначала выберите канал или группу для работы.\n"
                    "Используйте кнопку 'Сменить группу' в главном меню."
                )
                return
            
            # Сохраняем канал в состоянии
            await state.update_data(sheet_channel_id=user.current_chat_id)
            
            instructions_text = (
                "📊 <b>Подключение Google Таблицы</b>\n\n"
                "Для подключения таблицы выполните следующие шаги:\n\n"
                "1. Создайте <b>пустую</b> таблицу в Google Sheets\n"
                "2. Откройте доступ для редактирования следующему email:\n"
                f"<code>{GoogleSheetsClient.SERVICE_ACCOUNT}</code>\n\n"
                "3. Отправьте URL таблицы в формате:\n"
                "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit\n\n"
                "<i>Бот автоматически создаст необходимую структуру: листы 'Контент-план' и 'История' "
                "с нужными заголовками столбцов.</i>"
            )
            
            await message.answer(
                text=instructions_text,
                parse_mode="HTML"
            )
            
            await state.set_state(GoogleSheetStates.waiting_for_url)
            
    except Exception as e:
        logger.error(f"Error starting add sheet process: {e}")
        await message.answer("⚠️ Произошла ошибка при начале процесса добавления таблицы. Пожалуйста, попробуйте позже.")

@router.message(Command('syncsheet'))
async def sync_sheet_command(message: Message):
    """Ручной запуск синхронизации таблиц через команду"""
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await message.answer(
                    "⚠️ Сначала выберите канал или группу для работы.\n"
                    "Используйте кнопку 'Сменить группу' в главном меню."
                )
                return
            
            channel_id = user.current_chat_id
            
            # Получаем информацию о подключенных таблицах для этого канала
            sheets_q = select(GoogleSheet).filter(GoogleSheet.chat_id == channel_id, GoogleSheet.is_active == True)
            sheets_result = await session.execute(sheets_q)
            sheets = sheets_result.scalars().all()
            
            if not sheets:
                await message.answer("⚠️ У выбранного канала нет активных подключений к Google Таблицам.")
                return
            
            # Сообщаем о начале синхронизации
            status_message = await message.answer("🔄 Начинаю синхронизацию таблиц...")
            
            # Запускаем синхронизацию каждой таблицы
            from scheduler import check_google_sheets
            
            # Запускаем проверку таблиц
            await check_google_sheets(message.bot)
            
            # Сообщаем о завершении синхронизации
            await status_message.edit_text("✅ Синхронизация завершена успешно!")
            
    except Exception as e:
        logger.error(f"Error syncing sheets: {e}")
        await message.answer(f"❌ Ошибка при синхронизации таблиц: {str(e)}")

@router.message(GoogleSheetStates.waiting_for_url)
async def process_sheet_url(message: Message, state: FSMContext):
    """Обработка URL таблицы."""
    url = message.text.strip()
    
    # Проверяем формат URL
    if "docs.google.com/spreadsheets/d/" not in url:
        await message.answer(
            "❌ Неверный формат URL. Пожалуйста, отправьте корректный URL Google Таблицы в формате:\n"
            "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit"
        )
        return
    
    # Извлекаем ID таблицы
    spreadsheet_id = url.split("/d/")[1].split("/")[0]
    
    # Сохраняем ID таблицы
    await state.update_data(spreadsheet_id=spreadsheet_id)
    
    # Сообщение о процессе
    status_message = await message.answer("🔄 Проверяем доступ к таблице и создаем структуру...")
    
    # Проверяем доступ к таблице и создаем структуру
    try:
        sheets_client = GoogleSheetsClient()
        
        try:
            # Проверяем доступ к таблице
            metadata = sheets_client.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            
            # Если доступ есть, создаем структуру таблицы
            await status_message.edit_text("🔄 Доступ к таблице получен. Создаем необходимую структуру...")
            
            # Создаем структуру таблицы
            if sheets_client.create_sheet_structure(spreadsheet_id):
                # После успешного создания структуры
                sheet_name = "Контент-план"  # Используем значение по умолчанию
                
                # Сохраняем название листа
                await state.update_data(sheet_name=sheet_name)
                
                await status_message.edit_text(
                    f"✅ Структура таблицы создана успешно!\n\n"
                    f"Подготовлены листы 'Контент-план' и 'История'.\n"
                    f"В качестве рабочего листа будет использоваться '{sheet_name}'.\n\n"
                    f"Теперь укажите интервал синхронизации в минутах (как часто бот будет проверять таблицу).\n"
                    f"По умолчанию: 15 минут.\n\n"
                    f"Отправьте число от 5 до 120 или нажмите /default для использования значения по умолчанию."
                )
                
                # Переходим сразу к указанию интервала синхронизации
                await state.set_state(GoogleSheetStates.waiting_for_interval)
            else:
                await status_message.edit_text(
                    "❌ Не удалось создать структуру таблицы. Пожалуйста, проверьте права доступа и попробуйте снова."
                )
                
        except Exception as sheet_error:
            error_message = str(sheet_error)
            logger.error(f"Error accessing sheet: {error_message}")
            
            if "forbidden" in error_message.lower() or "permission" in error_message.lower():
                await status_message.edit_text(
                    f"❌ Ошибка доступа: у бота нет прав для работы с таблицей.\n\n"
                    f"Убедитесь, что вы предоставили доступ для редактирования email-адресу:\n"
                    f"<code>{GoogleSheetsClient.SERVICE_ACCOUNT}</code>\n\n"
                    f"После этого повторите попытку или используйте другую таблицу."
                )
            else:
                await status_message.edit_text(
                    f"❌ Ошибка при работе с таблицей:\n\n"
                    f"{error_message[:200]}...\n\n"
                    f"Попробуйте еще раз или используйте другую таблицу."
                )
        
    except Exception as e:
        logger.error(f"Error in sheet URL processing: {e}")
        await status_message.edit_text(
            "⚠️ Произошла ошибка при обработке URL таблицы. Пожалуйста, попробуйте позже."
        )

@router.message(GoogleSheetStates.waiting_for_interval)
async def process_sync_interval(message: Message, state: FSMContext):
    """Обработка интервала синхронизации."""
    interval_text = message.text.strip()
    
    # Проверяем, использует ли пользователь значение по умолчанию
    if interval_text == "/default":
        interval = 15
    else:
        try:
            interval = int(interval_text)
            if interval < 5 or interval > 120:
                await message.answer(
                    "❌ Интервал должен быть от 5 до 120 минут.\n"
                    "Попробуйте еще раз или отправьте /default для использования значения по умолчанию (15 минут)."
                )
                return
        except ValueError:
            await message.answer(
                "❌ Пожалуйста, введите целое число.\n"
                "Попробуйте еще раз или отправьте /default для использования значения по умолчанию (15 минут)."
            )
            return
    
    # Получаем все данные из состояния
    user_data = await state.get_data()
    spreadsheet_id = user_data.get("spreadsheet_id")
    sheet_name = user_data.get("sheet_name")
    channel_id = user_data.get("sheet_channel_id")
    
    # Создаем новую запись в БД
    try:
        async with AsyncSessionLocal() as session:
            new_sheet = GoogleSheet(
                chat_id=channel_id,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sync_interval=interval,
                created_by=message.from_user.id
            )
            
            session.add(new_sheet)
            await session.commit()
            
            await message.answer(
                f"🎉 Google Таблица успешно подключена!\n\n"
                f"<b>Параметры подключения:</b>\n"
                f"- ID таблицы: {spreadsheet_id}\n"
                f"- Лист: {sheet_name}\n"
                f"- Интервал синхронизации: {interval} минут\n\n"
                f"Бот будет автоматически проверять таблицу и публиковать посты по расписанию.\n"
                f"Используйте команду /syncsheet для немедленной синхронизации.",
                parse_mode="HTML"
            )
            
            # Очищаем состояние
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error saving sheet data: {e}")
        await message.answer(
            f"❌ Ошибка при сохранении данных: {str(e)}\n\n"
            f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
        )
        await state.clear()

@router.message(Command('removesheet'))
async def remove_sheet(message: Message):
    """Удаление подключения к Google Таблице"""
    user_id = message.from_user.id
    
    # Получаем номер таблицы из аргументов команды
    args = message.text.split()
    if len(args) != 2:
        await message.answer(
            "⚠️ Неверный формат команды. Используйте: /removesheet [номер]\n\n"
            "Например: /removesheet 1"
        )
        return
    
    try:
        sheet_number = int(args[1])
        if sheet_number < 1:
            raise ValueError("Sheet number must be positive")
    except ValueError:
        await message.answer("⚠️ Номер таблицы должен быть положительным целым числом.")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await message.answer(
                    "⚠️ Сначала выберите канал или группу для работы.\n"
                    "Используйте кнопку 'Сменить группу' в главном меню."
                )
                return
            
            channel_id = user.current_chat_id
            
            # Получаем список таблиц для этого канала
            sheets_q = select(GoogleSheet).filter(GoogleSheet.chat_id == channel_id).order_by(GoogleSheet.id)
            sheets_result = await session.execute(sheets_q)
            sheets = sheets_result.scalars().all()
            
            if not sheets:
                await message.answer("⚠️ У выбранного канала нет подключенных таблиц.")
                return
            
            if sheet_number > len(sheets):
                await message.answer(f"⚠️ У выбранного канала только {len(sheets)} подключенных таблиц.")
                return
            
            # Получаем таблицу для удаления
            sheet_to_remove = sheets[sheet_number - 1]
            
            # Помечаем таблицу как неактивную (мягкое удаление)
            sheet_to_remove.is_active = False
            await session.commit()
            
            await message.answer(
                f"✅ Таблица {sheet_to_remove.spreadsheet_id[:15]}... успешно отключена.\n\n"
                f"Для повторного подключения используйте команду /addsheet"
            )
            
    except Exception as e:
        logger.error(f"Error removing sheet: {e}")
        await message.answer("⚠️ Произошла ошибка при отключении таблицы. Пожалуйста, попробуйте позже.")

# Служебные функции для работы с базой данных таблиц
@router.message(Command('fix_sheets'))
async def fix_sheets_command(message: Message):
    """Служебная команда для исправления проблем с таблицами"""
    await fix_db_sheets(message)

async def fix_db_sheets(message: Message):
    """Служебная функция для проверки и исправления записей в БД таблиц"""
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    async with AsyncSessionLocal() as session:
        user_q = select(User).filter(User.user_id == user_id, User.role == "admin")
        user_result = await session.execute(user_q)
        user = user_result.scalar_one_or_none()
        
        if not user:
            await message.answer("⚠️ У вас недостаточно прав для выполнения этой команды.")
            return
        
        # Получаем все записи таблиц в БД
        sheets_q = select(GoogleSheet)
        sheets_result = await session.execute(sheets_q)
        all_sheets = sheets_result.scalars().all()
        
        # Статистика для отчета
        total_sheets = len(all_sheets)
        active_sheets = len([s for s in all_sheets if s.is_active])
        inactive_sheets = total_sheets - active_sheets
        
        await message.answer(
            f"📊 <b>Статистика таблиц в БД:</b>\n\n"
            f"Всего записей: {total_sheets}\n"
            f"Активных: {active_sheets}\n"
            f"Неактивных: {inactive_sheets}\n",
            parse_mode="HTML"
        )
        
        # Для проверки состояния по каналам
        channels_dict = {}
        for sheet in all_sheets:
            if sheet.chat_id not in channels_dict:
                channels_dict[sheet.chat_id] = {"active": 0, "inactive": 0}
            
            if sheet.is_active:
                channels_dict[sheet.chat_id]["active"] += 1
            else:
                channels_dict[sheet.chat_id]["inactive"] += 1
        
        # Статистика по каналам
        channels_info = []
        for chat_id, stats in channels_dict.items():
            try:
                group_q = select(Group).filter(Group.chat_id == chat_id)
                group_result = await session.execute(group_q)
                group = group_result.scalar_one_or_none()
                name = group.title if group else f"Канал #{chat_id}"
                channels_info.append(
                    f"- {name}: активных {stats['active']}, неактивных {stats['inactive']}"
                )
            except Exception as e:
                logger.error(f"Error getting channel info: {e}")
                channels_info.append(
                    f"- Канал #{chat_id}: активных {stats['active']}, неактивных {stats['inactive']}"
                )
        
        if channels_info:
            await message.answer(
                f"📈 <b>Таблицы по каналам:</b>\n\n" + "\n".join(channels_info),
                parse_mode="HTML"
            )
            
            # Предложение удалить призрачные активные записи
            if active_sheets > 0:
                await message.answer(
                    "Хотите удалить все активные записи таблиц? Это решит проблему с 'призрачными' таблицами.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Да, удалить все", callback_data="fix_sheets_confirm")],
                        [InlineKeyboardButton(text="❌ Нет, не удалять", callback_data="fix_sheets_cancel")]
                    ])
                )

@router.callback_query(lambda c: c.data == "fix_sheets_confirm")
async def fix_sheets_confirm(call: CallbackQuery):
    """Обработчик подтверждения удаления всех активных записей таблиц"""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем все активные записи таблиц
            sheets_q = select(GoogleSheet).filter(GoogleSheet.is_active == True)
            sheets_result = await session.execute(sheets_q)
            active_sheets = sheets_result.scalars().all()
            
            count = len(active_sheets)
            
            # Помечаем все таблицы как неактивные
            for sheet in active_sheets:
                sheet.is_active = False
            
            await session.commit()
            
            await call.message.edit_text(
                f"✅ Успешно деактивировано {count} записей таблиц.\n\n"
                f"Теперь при переходе в меню 'Таблицы' у каналов без подключенных таблиц "
                f"не будет отображаться кнопка 'Синхронизировать'."
            )
            
    except Exception as e:
        logger.error(f"Error fixing sheets: {e}")
        await call.message.edit_text(f"❌ Ошибка при исправлении записей: {e}")

@router.callback_query(lambda c: c.data == "fix_sheets_cancel")
async def fix_sheets_cancel(call: CallbackQuery):
    """Обработчик отмены удаления записей таблиц"""
    await call.message.edit_text("❌ Операция отменена. Записи таблиц не изменены.")
