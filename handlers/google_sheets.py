# google_sheets.py

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.base import StorageKey

from sqlalchemy import select
from sqlalchemy import func, and_
from sqlalchemy import select, text

from database.db import AsyncSessionLocal
from database.models import User, GoogleSheet, Group
from utils.google_sheets import GoogleSheetsClient

router = Router()
logger = logging.getLogger(__name__)
# Настраиваем детальное логирование
logger.setLevel(logging.INFO)

class GoogleSheetStates(StatesGroup):
    """Состояния для процесса добавления Google Таблицы"""
    waiting_for_url = State()
    waiting_for_sheet_name = State()
    waiting_for_interval = State()


# Добавляем GOOGLE таблицы

@router.message(lambda m: m.text == "Таблицы" or m.text == "Таблицы Google Sheets")
async def sheets_menu(message: Message, state: FSMContext):
    """Обработчик для текстовой кнопки 'Таблицы' или 'Таблицы Google Sheets'"""
    logger.info("Processing Таблицы text message")
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).filter(User.user_id == user_id))
            if not user or not user.current_chat_id:
                await message.answer("⚠️ Сначала выберите канал или группу.")
                return
            
            channel = await session.scalar(select(Group).filter(Group.chat_id == user.current_chat_id))
            if not channel:
                await message.answer("❌ Канал не найден.")
                return
            
            # Запрос активных таблиц
            active_sheets = await session.scalars(
                select(GoogleSheet).filter(
                    GoogleSheet.chat_id == channel.chat_id,
                    GoogleSheet.is_active == True
                )
            )
            active_sheets_list = active_sheets.all()
            
            # Логирование для отладки
            logger.info(f"Активные таблицы: {active_sheets_list}")
            logger.info(f"is_active значений: {[s.is_active for s in active_sheets_list]}")
            
            # Диагностическое логирование
            logger.info(f"Active sheets list length: {len(active_sheets_list)}")
            logger.info(f"Active sheets list details: {[{'id': s.id, 'chat_id': s.chat_id, 'is_active': s.is_active, 'active_type': type(s.is_active).__name__} for s in active_sheets_list]}")
            
            # Поиск активных таблиц
            has_active_sheets = False
            active_sheet_id = None
            if active_sheets_list:
                for sheet in active_sheets_list:
                    if sheet.is_active == 1 or sheet.is_active is True:
                        has_active_sheets = True
                        active_sheet_id = sheet.id
                        logger.info(f"Found active sheet: ID={active_sheet_id}, is_active={sheet.is_active}")
                        break
            
            logger.info(f"Has active sheets: {has_active_sheets}")
            
            # Формируем клавиатуру
            inline_keyboard = [
                [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")]
            ]
                        
            # Добавляем кнопки только если есть активные таблицы
            if has_active_sheets:
                inline_keyboard.append([InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")])
                inline_keyboard.append([InlineKeyboardButton(text="🗑 Удалить таблицу", callback_data=f"delete_sheet:{active_sheet_id}")])
                        
            inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])

            
            keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
            await message.answer(
                f"📊 Интеграция с Google Sheets для канала \"{channel.title}\"",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка в sheets_menu: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await message.answer("⚠️ Ошибка загрузки меню.")


# Обработчик для инлайн-кнопки в основном меню канала
@router.callback_query(lambda c: c.data == "open_sheets_menu")
async def open_sheets_menu_handler(call: CallbackQuery, state: FSMContext):
    """Обработчик для открытия меню Google таблиц по инлайн кнопке"""
    logger.info("Processing open_sheets_menu callback")
    
    user_id = call.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).filter(User.user_id == user_id))
            if not user or not user.current_chat_id:
                await call.answer("⚠️ Сначала выберите канал или группу.", show_alert=True)
                return
            
            channel = await session.scalar(select(Group).filter(Group.chat_id == user.current_chat_id))
            if not channel:
                await call.answer("❌ Канал не найден.", show_alert=True)
                return
            
            # Запрос активных таблиц
            active_sheets = await session.scalars(
                select(GoogleSheet).filter(
                    GoogleSheet.chat_id == channel.chat_id,
                    GoogleSheet.is_active == True
                )
            )
            active_sheets_list = active_sheets.all()
            
            # Логирование для отладки
            logger.info(f"Active sheets list from open_sheets_menu: {len(active_sheets_list)}")
            
            # Поиск активных таблиц
            has_active_sheets = False
            active_sheet_id = None
            if active_sheets_list:
                for sheet in active_sheets_list:
                    if sheet.is_active == 1 or sheet.is_active is True:
                        has_active_sheets = True
                        active_sheet_id = sheet.id
                        logger.info(f"Found active sheet: ID={active_sheet_id}")
                        break
            
            # Формируем клавиатуру
            inline_keyboard = [
                [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")]
            ]
                        
            # Добавляем кнопки только если есть активные таблицы
            if has_active_sheets:
                inline_keyboard.append([InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")])
                inline_keyboard.append([InlineKeyboardButton(text="🗑 Удалить таблицу", callback_data=f"delete_sheet:{active_sheet_id}")])
                        
            inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])

            
            keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
            await call.message.answer(
                f"📊 Интеграция с Google Sheets для канала \"{channel.title}\"",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # Отвечаем на коллбэк, чтобы убрать часики
            await call.answer()
            
    except Exception as e:
        logger.error(f"Ошибка в open_sheets_menu_handler: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await call.answer("⚠️ Ошибка загрузки меню.", show_alert=True)


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
            
            chat_id = sheet.chat_id  # Сохраняем chat_id перед деактивацией
            
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
            
            # Проверяем остались ли активные таблицы после удаления
            active_sheets_count_q = select(func.count()).select_from(GoogleSheet).where(
                and_(
                    GoogleSheet.chat_id == chat_id,
                    GoogleSheet.is_active == True
                )
            )
            active_sheets_count_result = await session.execute(active_sheets_count_q)
            active_sheets_count = active_sheets_count_result.scalar()
            
            logger.info(f"After deletion: {active_sheets_count} active sheets remain for channel {chat_id}")
            
            # Получаем имя канала для сообщения
            channel_q = select(Group).filter(Group.chat_id == chat_id)
            channel_result = await session.execute(channel_q)
            channel = channel_result.scalar_one_or_none()
            channel_title = channel.title if channel else "канала"
            
            # Показываем разные сообщения в зависимости от наличия оставшихся таблиц
            if active_sheets_count > 0:
                # Если остались активные таблицы - показываем клавиатуру с кнопкой синхронизации
                await call.message.edit_text(
                    f"📊 <b>Интеграция с Google Sheets для канала \"{channel_title}\"</b>\n\n"
                    f"Таблица успешно отключена. У вас осталось еще {active_sheets_count} активных таблиц.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")],
                        [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")],
                        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
                    ])
                )
            else:
                # Если не осталось активных таблиц - показываем клавиатуру без кнопки синхронизации
                await call.message.edit_text(
                    f"📊 <b>Интеграция с Google Sheets для канала \"{channel_title}\"</b>\n\n"
                    f"Таблица успешно отключена. У канала больше нет активных таблиц.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")],
                        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
                    ])
                )
                
    except Exception as e:
        logger.error(f"Error deleting sheet: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await call.answer("⚠️ Произошла ошибка при удалении таблицы", show_alert=True)

# Обработчик для кнопки "Подключить таблицу"
@router.callback_query(lambda c: c.data == "sheet_connect")
async def sheet_connect_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик для кнопки 'Подключить таблицу'"""
    logger.info("Processing sheet_connect callback")
    
    user_id = call.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user = await session.scalar(select(User).filter(User.user_id == user_id))
            
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
            
            # Отвечаем на коллбэк
            await call.answer()
            
            # Отправляем новое сообщение с инструкциями
            await call.message.answer(
                text=instructions_text,
                parse_mode="HTML"
            )
            
            # Устанавливаем состояние ожидания URL
            await state.set_state(GoogleSheetStates.waiting_for_url)
            
    except Exception as e:
        logger.error(f"Error in sheet_connect_callback: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await call.answer("⚠️ Произошла ошибка при начале процесса добавления таблицы", show_alert=True)

@router.callback_query(F.data == "sync_sheets_now")
async def sync_sheets_now_callback(call: CallbackQuery):
    """Обработчик для коллбэка синхронизации таблиц."""
    logger.info(f"Sync sheets callback received: {call.data}")
    
    # Код обработки синхронизации
    user_id = call.from_user.id
    
    try:
        # Первым делом показываем всплывающее уведомление, что запрос получен
        await call.answer("🔄 Запрос на синхронизацию получен", show_alert=False)
        
        # Отправляем сообщение о начале процесса
        status_message = await call.message.answer("🔄 <b>Начинаю синхронизацию таблиц...</b>\n\nЭтот процесс может занять некоторое время. Пожалуйста, подождите.", parse_mode="HTML")
        
        async with AsyncSessionLocal() as session:
            # Получаем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.current_chat_id:
                await status_message.edit_text("⚠️ Ошибка: не выбран канал или группа.")
                return
            
            channel_id = user.current_chat_id
            
            # Получаем информацию о канале для отображения
            channel_q = select(Group).filter(Group.chat_id == channel_id)
            channel_result = await session.execute(channel_q)
            channel = channel_result.scalar_one_or_none()
            channel_name = channel.title if channel else f"Канал {channel_id}"
            
            # Обновляем статусное сообщение
            await status_message.edit_text(
                f"🔄 <b>Синхронизация для канала \"{channel_name}\"</b>\n\n"
                f"Проверяю подключенные таблицы...",
                parse_mode="HTML"
            )
            
            # Получаем информацию о подключенных таблицах для этого канала
            sheets_q = select(GoogleSheet).filter(GoogleSheet.chat_id == channel_id, GoogleSheet.is_active == True)
            sheets_result = await session.execute(sheets_q)
            sheets = sheets_result.scalars().all()
            
            if not sheets:
                await status_message.edit_text(
                    f"⚠️ <b>Для канала \"{channel_name}\" не найдено активных таблиц</b>\n\n"
                    f"Сначала подключите таблицу, используя кнопку «Подключить таблицу».",
                    parse_mode="HTML"
                )
                return
            
            # Обновляем статусное сообщение
            sheet_count = len(sheets)
            sheet_names = ", ".join([f"<code>{sheet.spreadsheet_id[:8]}...</code>" for sheet in sheets[:3]])
            if sheet_count > 3:
                sheet_names += f" и еще {sheet_count - 3}"
                
            await status_message.edit_text(
                f"🔄 <b>Синхронизация для канала \"{channel_name}\"</b>\n\n"
                f"Найдено таблиц: {sheet_count}\n"
                f"ID таблиц: {sheet_names}\n\n"
                f"Выполняю синхронизацию...",
                parse_mode="HTML"
            )
            
            # Запускаем синхронизацию каждой таблицы
            from scheduler import check_google_sheets
            
            # Запускаем проверку таблиц
            try:
                await check_google_sheets(call.bot)
                
                # Сообщаем о завершении синхронизации
                await status_message.edit_text(
                    f"✅ <b>Синхронизация успешно завершена!</b>\n\n"
                    f"Канал: \"{channel_name}\"\n"
                    f"Таблиц обработано: {sheet_count}\n\n"
                    f"Все запланированные посты из таблиц обработаны.",
                    parse_mode="HTML"
                )
            except Exception as sync_error:
                logger.error(f"Error during synchronization: {sync_error}")
                await status_message.edit_text(
                    f"⚠️ <b>Ошибка при синхронизации таблиц</b>\n\n"
                    f"Канал: \"{channel_name}\"\n"
                    f"Причина ошибки: {str(sync_error)[:100]}...\n\n"
                    f"Попробуйте повторить синхронизацию позже или проверьте доступ к таблицам.",
                    parse_mode="HTML"
                )
            
    except Exception as e:
        logger.error(f"Error in sync_sheets_now_callback: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Отправляем сообщение об ошибке, даже если предыдущие сообщения не удалось отправить
        try:
            await call.message.answer(
                f"❌ <b>Ошибка при синхронизации таблиц</b>\n\n"
                f"Причина: {str(e)[:200]}\n\n"
                f"Попробуйте повторить позже.",
                parse_mode="HTML"
            )
        except Exception:
            # Если и это не удалось, хотя бы покажем всплывающее уведомление
            await call.answer("❌ Ошибка при синхронизации. Проверьте подключение к интернету.", show_alert=True)

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
    
    # Получаем данные о выбранном канале
    user_data = await state.get_data()
    channel_id = user_data.get("sheet_channel_id")
    
    # Проверяем доступ к таблице и создаем структуру
    try:
        sheets_client = GoogleSheetsClient()
        
        try:
            # Проверяем доступ к таблице
            metadata = sheets_client.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            
            # Если доступ есть, получаем информацию о канале
            async with AsyncSessionLocal() as session:
                channel_q = select(Group).filter(Group.chat_id == channel_id)
                channel_result = await session.execute(channel_q)
                channel = channel_result.scalar_one_or_none()
                
                chat_title = None
                if channel:
                    chat_title = channel.title or channel.display_name or f"Канал {channel_id}"
                
                # Создаем структуру таблицы, передавая информацию о канале
                await status_message.edit_text("🔄 Доступ к таблице получен. Создаем необходимую структуру...")
                
                success = sheets_client.create_sheet_structure(
                    spreadsheet_id,
                    chat_id=channel_id,
                    chat_title=chat_title
                )
                
                if success:
                    # После успешного создания структуры
                    sheet_name = "Контент-план"  # Используем значение по умолчанию
                    
                    # Сохраняем название листа
                    await state.update_data(sheet_name=sheet_name)
                    
                    await status_message.edit_text(
                        f"✅ Структура таблицы создана успешно!\n\n"
                        f"Подготовлены листы 'Контент-план' и 'История'.\n"
                        f"В качестве рабочего листа будет использоваться '{sheet_name}'.\n\n"
                        f"<b>Важно:</b> При заполнении таблицы используйте следующие форматы:\n"
                        f"• Дата: ДД.ММ.ГГГГ (например, 16.05.2025)\n"
                        f"• Время: ЧЧ:ММ (например, 14:30)\n"
                        f"• ID канала: используйте автоматически заполненное значение\n"
                        f"• Статус: выбирайте из выпадающего списка\n\n"
                        f"Теперь укажите интервал синхронизации в минутах (как часто бот будет проверять таблицу).\n"
                        f"По умолчанию: 15 минут.\n\n"
                        f"Отправьте число от 5 до 120 или нажмите /default для использования значения по умолчанию.",
                        parse_mode="HTML"
                    )
                    
                    # Переходим к указанию интервала синхронизации
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
            # Деактивируем все старые записи для этого канала (для чистоты)
            from sqlalchemy import update
            await session.execute(
                update(GoogleSheet)
                .where(GoogleSheet.chat_id == channel_id)
                .values(is_active=False)
            )
            
            # Создаем новую запись таблицы
            new_sheet = GoogleSheet(
                chat_id=channel_id,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sync_interval=interval,
                created_by=message.from_user.id,
                is_active=True  # Явно указываем, что таблица активна
            )
            
            session.add(new_sheet)
            await session.commit()

            # Получаем ID новой записи
            new_sheet_id = new_sheet.id
            logger.info(f"Created new sheet: ID={new_sheet_id}, active={new_sheet.is_active}")
            
            await message.answer(
                f"🎉 Google Таблица успешно подключена!\n\n"
                f"<b>Параметры подключения:</b>\n"
                f"- ID таблицы: {spreadsheet_id}\n"
                f"- Лист: {sheet_name}\n"
                f"- Интервал синхронизации: {interval} минут\n\n"
                f"Бот будет автоматически проверять таблицу и публиковать посты по расписанию.\n"
                f"Используйте кнопку 'Синхронизировать' для немедленной синхронизации.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")],
                    [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_main")]
                ])
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

@router.callback_query(lambda c: c.data == "back_to_sheets")
async def return_to_sheets_menu(call: CallbackQuery, state: FSMContext):
    """Новый обработчик для возврата в меню таблиц"""
    await call.answer()
    
    user_id = call.from_user.id
    await call.message.edit_text("🔄 Загрузка меню таблиц...")
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).filter(User.user_id == user_id))
            if not user or not user.current_chat_id:
                await call.message.edit_text("⚠️ Сначала выберите канал или группу.")
                return
            
            channel = await session.scalar(select(Group).filter(Group.chat_id == user.current_chat_id))
            if not channel:
                await call.message.edit_text("❌ Канал не найден.")
                return
            
            # Используем прямой SQL-запрос только для логирования
            check_query = text(f"SELECT COUNT(*) FROM google_sheets WHERE chat_id = {channel.chat_id} AND is_active = 1")
            check_result = await session.execute(check_query)
            check_count = check_result.scalar_one()
            logger.info(f"SQL query count for active sheets: {check_count}")
            
            # Запрос активных таблиц через ORM
            active_sheets_list = await session.scalars(
                select(GoogleSheet).filter(
                    GoogleSheet.chat_id == channel.chat_id,
                    GoogleSheet.is_active == True
                )
            )
            active_sheets = active_sheets_list.all()
            logger.info(f"ORM query found {len(active_sheets)} active sheets")
            
            # Всегда создаем базовую клавиатуру только с кнопкой добавления
            buttons = [
                [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")]
            ]
            
            # И добавляем кнопку синхронизации только если есть активные таблицы
            if active_sheets:
                sheet_id = active_sheets[0].id
                buttons.append([InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")])
                buttons.append([InlineKeyboardButton(text="🗑 Удалить таблицу", callback_data=f"delete_sheet:{sheet_id}")])
            
            # Всегда добавляем кнопку назад
            buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            # Отправляем сообщение с клавиатурой
            await call.message.edit_text(
                f"📊 Интеграция с Google Sheets для канала \"{channel.title}\"",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка в return_to_sheets_menu: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await call.message.edit_text("⚠️ Ошибка загрузки меню таблиц.")


@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_menu(call: CallbackQuery):
    """Обработчик для возврата в главное меню"""
    # Создаем главную клавиатуру
    from utils.keyboards import create_main_keyboard
    main_kb = await create_main_keyboard()
    
    # Отправляем сообщение с главным меню
    await call.message.answer("Выберите действие:", reply_markup=main_kb)
    
    # Скрываем инлайн-клавиатуру в предыдущем сообщении
    await call.message.edit_reply_markup(reply_markup=None)
    
    # Отвечаем на коллбэк
    await call.answer()
