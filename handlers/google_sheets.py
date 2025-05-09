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
    logger.info("Entering sheets_menu function")
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
                
                # Логируем создание клавиатуры
                logger.info("Creating keyboard for sheets with sheet_connect and sync_sheets_now buttons")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Подключить новую таблицу", callback_data="sheet_connect")],
                    [InlineKeyboardButton(text="🔄 Синхронизировать сейчас", callback_data="sync_sheets_now")]
                ])
                logger.info(f"Keyboard created with buttons: sheet_connect, sync_sheets_now")
                
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
                # Логируем создание клавиатуры для пустого списка
                logger.info("Creating keyboard for empty sheets list with sheet_connect button")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")]
                ])
                logger.info(f"Keyboard created with button: sheet_connect")
                
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

# Обработчик для отладки всех коллбэков
@router.callback_query()
# Обработчик для отладки всех коллбэков
@router.callback_query()
async def debug_callback(call: CallbackQuery, state: FSMContext):
    """Отладочный обработчик для всех коллбэков."""
    logger.info(f"Debug callback received: {call.data}")
    
    # Отдельно обрабатываем известные коллбэки
    if call.data == "sheet_connect" or call.data == "add_sheet":
        await handle_add_sheet_callback(call, state)
    elif call.data == "sync_sheets_now":
        await sync_sheets_now_callback(call)
    else:
        # Для неизвестных коллбэков показываем уведомление
        await call.answer(f"Получен коллбэк: {call.data}", show_alert=True)


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


@router.callback_query(F.data == "sync_sheets_now")
async def sync_sheets_now_callback(call: CallbackQuery):
    """Ручной запуск синхронизации таблиц через инлайн-кнопку"""
    logger.info("Processing sync_sheets_now callback")
    
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
            
            await message.answer(
                text=instructions_text,
                parse_mode="HTML"
            )
            
            await state.set_state(GoogleSheetStates.waiting_for_url)
            
    except Exception as e:
        logger.error(f"Error starting add sheet process: {e}")
        await message.answer("⚠️ Произошла ошибка при начале процесса добавления таблицы. Пожалуйста, попробуйте позже.")

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

