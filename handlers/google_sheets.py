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

class GoogleSheetStates(StatesGroup):
    """Состояния для процесса добавления Google Таблицы"""
    waiting_for_url = State()
    waiting_for_sheet_name = State()
    waiting_for_interval = State()

# Добавьте эти функции в начало файла после импортов и до определения обработчиков

def create_sync_button():
    """Создает стандартную кнопку синхронизации"""
    return InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sync_sheets_now")

def create_connect_button():
    """Создает стандартную кнопку подключения таблицы"""
    return InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")

def create_back_button():
    """Создает стандартную кнопку возврата в главное меню"""
    return InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")

def create_delete_button(sheet_id):
    """Создает кнопку удаления таблицы для конкретного ID"""
    return InlineKeyboardButton(text="🗑 Удалить таблицу", callback_data=f"delete_sheet:{sheet_id}")

def create_sheets_keyboard(has_active_sheets=False, active_sheet_id=None):
    """
    Создает стандартную клавиатуру для меню таблиц
    
    Args:
        has_active_sheets: Есть ли активные таблицы
        active_sheet_id: ID активной таблицы для кнопки удаления
        
    Returns:
        InlineKeyboardMarkup: Готовая клавиатура с кнопками
    """
    inline_keyboard = [
        [create_connect_button()]
    ]
    
    if has_active_sheets and active_sheet_id is not None:
        inline_keyboard.append([create_sync_button()])
        inline_keyboard.append([create_delete_button(active_sheet_id)])
    
    inline_keyboard.append([create_back_button()])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

@router.message(lambda m: m.text == "Таблицы")
async def sheets_menu(message: Message, state: FSMContext):
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
            logger.info(f"Активные таблицы: {len(active_sheets_list)}")
            
            # Поиск активных таблиц
            has_active_sheets = False
            active_sheet_id = None
            if active_sheets_list:
                for sheet in active_sheets_list:
                    if sheet.is_active == 1 or sheet.is_active is True:
                        has_active_sheets = True
                        active_sheet_id = sheet.id
                        break
            
            # Создаем клавиатуру с помощью вспомогательной функции
            keyboard = create_sheets_keyboard(has_active_sheets, active_sheet_id)
            
            await message.answer(
                f"📊 Интеграция с Google Sheets для канала \"{channel.title}\"",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("⚠️ Ошибка загрузки меню.")

@router.callback_query(lambda c: c.data == "open_sheets_menu")
async def open_sheets_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик для инлайн-кнопки 'Таблицы Google Sheets'"""
    user_id = callback.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).filter(User.user_id == user_id))
            if not user or not user.current_chat_id:
                await callback.answer("⚠️ Сначала выберите канал или группу.", show_alert=True)
                return
            
            channel = await session.scalar(select(Group).filter(Group.chat_id == user.current_chat_id))
            if not channel:
                await callback.answer("❌ Канал не найден.", show_alert=True)
                return
            
            # Запрос активных таблиц
            active_sheets = await session.scalars(
                select(GoogleSheet).filter(
                    GoogleSheet.chat_id == channel.chat_id,
                    GoogleSheet.is_active == True
                )
            )
            active_sheets_list = active_sheets.all()
            
            # Поиск активных таблиц
            has_active_sheets = False
            active_sheet_id = None
            if active_sheets_list:
                for sheet in active_sheets_list:
                    if sheet.is_active == 1 or sheet.is_active is True:
                        has_active_sheets = True
                        active_sheet_id = sheet.id
                        break
            
            # Создаем клавиатуру с помощью вспомогательной функции
            keyboard = create_sheets_keyboard(has_active_sheets, active_sheet_id)
            
            await callback.message.answer(
                f"📊 Интеграция с Google Sheets для канала \"{channel.title}\"",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("⚠️ Ошибка загрузки меню.", show_alert=True)

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
            
            chat_id = sheet.chat_id
            
            # Проверки прав пользователя...
            
            # Помечаем таблицу как неактивную
            sheet.is_active = False
            await session.commit()
            
            # Отправляем сообщение об успешном удалении
            await call.answer("✅ Таблица успешно отключена", show_alert=False)
            
            # Проверяем оставшиеся активные таблицы...
            # Получаем имя канала...
            
            # Создаем и отображаем клавиатуру с учетом оставшихся таблиц
            active_sheets_count = await session.scalar(
                select(func.count()).select_from(GoogleSheet).where(
                    and_(
                        GoogleSheet.chat_id == chat_id,
                        GoogleSheet.is_active == True
                    )
                )
            )
            
            channel = await session.scalar(select(Group).filter(Group.chat_id == chat_id))
            channel_title = channel.title if channel else "канала"
            
            # Используем вспомогательную функцию для создания клавиатуры
            # Но сначала нужно получить id другой активной таблицы, если она есть
            active_sheet_id = None
            if active_sheets_count > 0:
                active_sheet = await session.scalar(
                    select(GoogleSheet).filter(
                        GoogleSheet.chat_id == chat_id,
                        GoogleSheet.is_active == True
                    ).limit(1)
                )
                if active_sheet:
                    active_sheet_id = active_sheet.id
            
            # Создаем клавиатуру
            keyboard = create_sheets_keyboard(active_sheets_count > 0, active_sheet_id)
            
            # Обновляем текст сообщения
            message_text = (
                f"📊 <b>Интеграция с Google Sheets для канала \"{channel_title}\"</b>\n\n"
                f"Таблица успешно отключена."
            )
            
            if active_sheets_count > 0:
                message_text += f" У вас осталось еще {active_sheets_count} активных таблиц."
            else:
                message_text += " У канала больше нет активных таблиц."
            
            await call.message.edit_text(
                message_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error deleting sheet: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await call.answer("⚠️ Произошла ошибка при удалении таблицы", show_alert=True)

@router.message(GoogleSheetStates.waiting_for_interval)
async def process_sync_interval(message: Message, state: FSMContext):
    """Обработка интервала синхронизации."""
    # ... (начало функции остается без изменений) ...
    
    # После успешного создания новой записи в БД
    try:
        # ... (весь код создания записи в БД) ...
        
        # Получаем ID новой записи
        new_sheet_id = new_sheet.id
        logger.info(f"Created new sheet: ID={new_sheet_id}, active={new_sheet.is_active}")
        
        # Создаем клавиатуру с кнопкой синхронизации, используя helper-функции
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [create_sync_button()],
            [create_back_button()]
        ])
        
        await message.answer(
            f"🎉 Google Таблица успешно подключена!\n\n"
            f"<b>Параметры подключения:</b>\n"
            f"- ID таблицы: {spreadsheet_id}\n"
            f"- Лист: {sheet_name}\n"
            f"- Интервал синхронизации: {interval} минут\n\n"
            f"Бот будет автоматически проверять таблицу и публиковать посты по расписанию.\n"
            f"Используйте кнопку 'Синхронизировать' для немедленной синхронизации.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        # ... (обработка ошибок остается без изменений) ...

@router.callback_query(lambda c: c.data == "back_to_sheets")
async def return_to_sheets_menu(call: CallbackQuery, state: FSMContext):
    """Обработчик для возврата в меню таблиц"""
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
            
            # Запрос активных таблиц
            active_sheets_list = await session.scalars(
                select(GoogleSheet).filter(
                    GoogleSheet.chat_id == channel.chat_id,
                    GoogleSheet.is_active == True
                )
            )
            active_sheets = active_sheets_list.all()
            logger.info(f"ORM query found {len(active_sheets)} active sheets")
            
            # Поиск активных таблиц
            has_active_sheets = False
            active_sheet_id = None
            if active_sheets:
                for sheet in active_sheets:
                    if sheet.is_active == 1 or sheet.is_active is True:
                        has_active_sheets = True
                        active_sheet_id = sheet.id
                        break
            
            # Используем вспомогательную функцию для создания клавиатуры
            keyboard = create_sheets_keyboard(has_active_sheets, active_sheet_id)
            
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

