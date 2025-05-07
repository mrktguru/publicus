# handlers/google_sheets.py
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
    # Получаем текущий выбранный канал
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
            sheets_q = select(GoogleSheet).filter(GoogleSheet.chat_id == channel_id)
            sheets_result = await session.execute(sheets_q)
            sheets = sheets_result.scalars().all()
        
            # Формируем ответное сообщение
            if sheets:
                sheets_text = "\n".join([
                    f"{i+1}. Таблица {sheet.spreadsheet_id[:15]}... "
                    f"(лист: {sheet.sheet_name}, "
                    f"последняя синхронизация: {sheet.last_sync.strftime('%d.%m.%Y %H:%M') if sheet.last_sync else 'никогда'})"
                    for i, sheet in enumerate(sheets)
                ])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Подключить новую таблицу", callback_data="add_sheet")],
                    [InlineKeyboardButton(text="🔄 Синхронизировать сейчас", callback_data="sync_sheets_now")]
                ])
                
                await message.answer(
                    f"📊 <b>Подключенные Google Таблицы</b>\n\n"
                    f"{sheets_text}\n\n"
                    f"Для управления таблицами используйте кнопки ниже или команды:\n"
                    f"/addsheet - подключить новую таблицу\n"
                    f"/removesheet [номер] - отключить таблицу\n"
                    f"/syncsheet [номер] - синхронизировать сейчас\n"
                    f"/sheetinfo [номер] - информация о подключении",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="add_sheet")]
                ])
                
                await message.answer(
                    "📊 <b>Google Таблицы</b>\n\n"
                    "У этого канала пока нет подключенных таблиц.\n\n"
                    "Чтобы подключить таблицу, нажмите кнопку ниже или используйте команду /addsheet.\n\n"
                    "<i>Для работы с таблицами вам необходимо:</i>\n"
                    "1. Создать таблицу в Google Sheets\n"
                    "2. Настроить доступ для сервисного аккаунта бота\n"
                    "3. Скопировать URL таблицы",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            
    except Exception as e:
        logger.error(f"Error showing sheets menu: {e}")
        await message.answer("⚠️ Произошла ошибка при получении данных о таблицах. Пожалуйста, попробуйте позже.")

@router.callback_query(lambda c: c.data == "add_sheet")
@router.message(Command('addsheet'))
async def add_sheet_start(message: Message | CallbackQuery, state: FSMContext):
    """Начало процесса добавления новой таблицы."""
    # Определяем, какой был источник команды - коллбэк или сообщение
    is_callback = isinstance(message, CallbackQuery)
    
    if is_callback:
        user_id = message.from_user.id
        actual_message = message.message
    else:
        user_id = message.from_user.id
        actual_message = message
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                if is_callback:
                    await message.answer("⚠️ Сначала выберите канал или группу")
                else:
                    await actual_message.answer(
                        "⚠️ Сначала выберите канал или группу для работы.\n"
                        "Используйте кнопку 'Сменить группу' в главном меню."
                    )
                return
            
            # Сохраняем канал в состоянии
            await state.update_data(sheet_channel_id=user.current_chat_id)
            
            instructions_text = (
                "📊 <b>Подключение Google Таблицы</b>\n\n"
                "Для подключения таблицы выполните следующие шаги:\n\n"
                "1. Создайте таблицу в Google Sheets\n"
                "2. Добавьте в таблицу листы 'Контент-план' и 'История'\n"
                "3. В лист 'Контент-план' добавьте столбцы:\n"
                "   - ID\n"
                "   - Канал/Группа\n"
                "   - Дата публикации (ДД.ММ.ГГГГ)\n"
                "   - Время публикации (ЧЧ:ММ)\n"
                "   - Заголовок\n"
                "   - Текст\n"
                "   - Медиа\n"
                "   - Статус\n"
                "   - Комментарии\n\n"
                "4. Откройте доступ к таблице для следующего email:\n"
                "<code>service-account@your-project.iam.gserviceaccount.com</code>\n\n"
                "Теперь отправьте полный URL таблицы в формате:\n"
                "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit"
            )
            
            if is_callback:
                await message.message.edit_text(
                    text=instructions_text,
                    parse_mode="HTML"
                )
            else:
                await actual_message.answer(
                    text=instructions_text,
                    parse_mode="HTML"
                )
            
            await state.set_state(GoogleSheetStates.waiting_for_url)
            
    except Exception as e:
        logger.error(f"Error starting add sheet process: {e}")
        error_message = "⚠️ Произошла ошибка при начале процесса добавления таблицы. Пожалуйста, попробуйте позже."
        
        if is_callback:
            await message.answer(error_message)
        else:
            await actual_message.answer(error_message)

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
    
    # Проверяем доступ к таблице
    try:
        sheets_client = GoogleSheetsClient()
        # Пробуем получить данные из таблицы
        try:
            _ = sheets_client.get_sheet_data(spreadsheet_id, "Контент-план!A1:B1")
            
            await message.answer(
                "✅ Доступ к таблице проверен успешно!\n\n"
                "Теперь укажите название листа с контент-планом.\n"
                "По умолчанию используется 'Контент-план'.\n\n"
                "Отправьте название листа или нажмите /default для использования значения по умолчанию."
            )
            
            await state.set_state(GoogleSheetStates.waiting_for_sheet_name)
            
        except Exception as sheet_error:
            logger.error(f"Error accessing sheet: {sheet_error}")
            await message.answer(
                f"❌ Ошибка при проверке доступа к таблице!\n\n"
                f"Убедитесь, что:\n"
                f"1. URL таблицы указан правильно\n"
                f"2. У сервисного аккаунта есть доступ к таблице\n"
                f"3. В таблице есть лист 'Контент-план'\n\n"
                f"Подробная ошибка: {str(sheet_error)[:100]}\n\n"
                f"Попробуйте еще раз или отправьте /cancel для отмены."
            )
        
    except Exception as e:
        logger.error(f"Error in sheet URL processing: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке URL таблицы. Пожалуйста, попробуйте позже."
        )

@router.message(GoogleSheetStates.waiting_for_sheet_name)
async def process_sheet_name(message: Message, state: FSMContext):
    """Обработка названия листа."""
    sheet_name = message.text.strip()
    
    # Проверяем, использует ли пользователь значение по умолчанию
    if sheet_name == "/default":
        sheet_name = "Контент-план"
    
    # Сохраняем название листа
    await state.update_data(sheet_name=sheet_name)
    
    await message.answer(
        f"✅ Выбран лист: {sheet_name}\n\n"
        f"Укажите интервал синхронизации в минутах (как часто бот будет проверять таблицу).\n"
        f"По умолчанию: 15 минут.\n\n"
        f"Отправьте число от 5 до 120 или нажмите /default для использования значения по умолчанию."
    )
    
    await state.set_state(GoogleSheetStates.waiting_for_interval)

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

@router.callback_query(lambda c: c.data == "sync_sheets_now")
@router.message(Command('syncsheet'))
async def sync_sheets_now(message: Message | CallbackQuery):
    """Ручной запуск синхронизации таблиц"""
    # Определяем, какой был источник команды - коллбэк или сообщение
    is_callback = isinstance(message, CallbackQuery)
    
    if is_callback:
        user_id = message.from_user.id
        actual_message = message.message
    else:
        user_id = message.from_user.id
        actual_message = message
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                if is_callback:
                    await message.answer("⚠️ Сначала выберите канал или группу")
                else:
                    await actual_message.answer(
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
                response_text = "⚠️ У выбранного канала нет активных подключений к Google Таблицам."
                
                if is_callback:
                    await message.answer(response_text)
                else:
                    await actual_message.answer(response_text)
                return
            
            # Сообщаем о начале синхронизации
            response_text = "🔄 Начинаю синхронизацию таблиц..."
            
            if is_callback:
                await message.answer(response_text)
                await actual_message.answer(response_text)
            else:
                processing_msg = await actual_message.answer(response_text)
            
            # Запускаем синхронизацию каждой таблицы
            from scheduler import check_google_sheets
            
            # Запускаем проверку таблиц
            await check_google_sheets(actual_message.bot)
            
            # Сообщаем о завершении синхронизации
            response_text = "✅ Синхронизация завершена успешно!"
            
            if is_callback:
                await actual_message.answer(response_text)
            else:
                await processing_msg.edit_text(response_text)
            
    except Exception as e:
        logger.error(f"Error syncing sheets: {e}")
        error_text = f"❌ Ошибка при синхронизации таблиц: {str(e)}"
        
        if is_callback:
            await message.answer(error_text)
        else:
            await actual_message.answer(error_text)

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
