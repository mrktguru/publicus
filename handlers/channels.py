import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from database.db import AsyncSessionLocal
from database.models import User, Group
from utils.keyboards import create_channels_keyboard, create_main_keyboard

router = Router()
logger = logging.getLogger(__name__)

class ChannelStates(StatesGroup):
    """Состояния для процесса добавления и управления каналами/группами"""
    waiting_for_channel_message = State()
    waiting_for_channel_username = State()
    waiting_for_group_command = State()
    waiting_for_display_name = State()

async def validate_channel_ownership(user_id: int, chat_id: int) -> bool:
    """Проверяет, принадлежит ли канал пользователю"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Group).where(
                Group.chat_id == chat_id,
                Group.added_by == user_id
            )
        )
        return result.scalar_one_or_none() is not None

async def update_user_current_chat(user_id: int, chat_id: int):
    """Обновляет текущий выбранный чат пользователя"""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(current_chat_id=chat_id)
            )
            await session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating user current chat: {e}")
            raise

@router.callback_query(lambda c: c.data == "add_channel")
async def add_channel_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик inline-кнопки для добавления канала"""
    try:
        await call.message.edit_text(
            "📌 Что вы хотите добавить?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📣 Канал", callback_data="add_channel_type")],
                [InlineKeyboardButton(text="👥 Группу", callback_data="add_group_type")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_channels")]
            ])
        )
    except Exception as e:
        logger.error(f"Error in add_channel_callback: {e}")
        await call.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(lambda c: c.data == "add_channel_type")
async def process_add_channel(call: CallbackQuery, state: FSMContext):
    """Обработчик для добавления канала"""
    try:
        await state.update_data(adding_type="channel")
        bot_username = call.bot.username
        await call.message.edit_text(
            f"📣 <b>Добавление нового канала</b>\n\n"
            f"Для добавления канала выполните следующие шаги:\n\n"
            f"1) Добавьте бота @{bot_username} администратором в канал\n"
            f"2) Убедитесь, что у бота есть права на публикацию сообщений\n"
            f"3) Перешлите любое сообщение из канала в этот чат\n"
            f"<b>ИЛИ</b>\n"
            f"Отправьте @username канала (если он публичный)",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_add_select")]
            ])
        )
        await state.set_state(ChannelStates.waiting_for_channel_message)
    except Exception as e:
        logger.error(f"Error in process_add_channel: {e}")
        await call.answer("Произошла ошибка. Попробуйте позже.")

@router.message(ChannelStates.waiting_for_channel_message)
async def process_channel_message(message: Message, state: FSMContext):
    """Обработка пересланного сообщения из канала или @username"""
    user_id = message.from_user.id
    
    try:
        # Обработка @username канала
        if message.text and message.text.startswith('@'):
            channel_username = message.text.strip()
            if not re.match(r'^@[a-zA-Z0-9_]{5,32}$', channel_username):
                await message.answer("⚠️ Некорректный username канала. Должен начинаться с @ и содержать 5-32 символов (a-z, 0-9, _)")
                return
                
            await state.update_data(channel_username=channel_username)
            await message.answer(
                f"🔄 Обрабатываю канал {channel_username}...\n\n"
                f"Пожалуйста, введите удобное название для этого канала:"
            )
            await state.set_state(ChannelStates.waiting_for_display_name)
            return

        # Обработка пересланного сообщения
        if not message.forward_from_chat or message.forward_from_chat.type != "channel":
            await message.answer(
                "⚠️ Это не пересланное сообщение из канала. Пожалуйста, перешлите сообщение из канала "
                "или отправьте @username публичного канала."
            )
            return

        chat = message.forward_from_chat
        async with AsyncSessionLocal() as session:
            # Проверка существования канала
            existing_group = await session.execute(
                select(Group).where(Group.chat_id == chat.id)
            )
            if existing_group.scalar_one_or_none():
                await message.answer("⚠️ Этот канал уже добавлен в систему.")
                await state.clear()
                return

            # Добавление нового канала
            new_group = Group(
                chat_id=chat.id,
                title=chat.title,
                username=chat.username,
                display_name=chat.title,
                type="channel",
                added_by=user_id,
                is_active=True
            )
            session.add(new_group)
            await session.commit()

            # Обновление текущего чата пользователя
            await update_user_current_chat(user_id, chat.id)

            await message.answer(
                f"✅ Канал \"{chat.title}\" успешно добавлен!\n\n"
                f"Теперь вы можете создавать контент для этого канала."
            )

            # Показ списка каналов
            keyboard = await create_channels_keyboard(user_id)
            await message.answer(
                "📝 <b>Выберите канал для работы</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await state.clear()

    except Exception as e:
        logger.error(f"Error in process_channel_message: {e}")
        await message.answer("⚠️ Произошла ошибка при добавлении канала.")
        await state.clear()

@router.message(ChannelStates.waiting_for_display_name)
async def process_display_name(message: Message, state: FSMContext):
    """Обработка ввода пользовательского имени для канала"""
    user_id = message.from_user.id
    display_name = message.text.strip()
    
    if not display_name or len(display_name) > 100:
        await message.answer("⚠️ Название должно содержать 1-100 символов.")
        return

    try:
        user_data = await state.get_data()
        channel_username = user_data.get("channel_username")
        username_without_at = channel_username.lstrip('@')

        async with AsyncSessionLocal() as session:
            # Проверка существования канала
            existing_group = await session.execute(
                select(Group).where(Group.username == username_without_at)
            )
            if existing_group.scalar_one_or_none():
                await message.answer(f"⚠️ Канал {channel_username} уже добавлен.")
                await state.clear()
                return

            # Добавление канала
            new_group = Group(
                chat_id=0,  # Временно 0, будет обновлено при проверке
                title=display_name,
                username=username_without_at,
                display_name=display_name,
                type="channel",
                added_by=user_id,
                is_active=True
            )
            session.add(new_group)
            await session.commit()

            # Обновление текущего чата пользователя
            await update_user_current_chat(user_id, new_group.id)

            await message.answer(
                f"✅ Канал {channel_username} добавлен как \"{display_name}\"!\n\n"
                f"⚠️ <b>Важно:</b> добавьте бота @{message.bot.username} в канал как администратора.",
                parse_mode="HTML"
            )

            keyboard = await create_channels_keyboard(user_id)
            await message.answer(
                "📝 <b>Выберите канал для работы</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await state.clear()

    except Exception as e:
        logger.error(f"Error in process_display_name: {e}")
        await message.answer("⚠️ Произошла ошибка при добавлении канала.")
        await state.clear()

@router.callback_query(lambda c: c.data.startswith("select_channel_"))
async def process_channel_selection(call: CallbackQuery):
    """Обработка выбора канала/группы"""
    user_id = call.from_user.id
    channel_id = int(call.data.split("_")[2])
    
    try:
        async with AsyncSessionLocal() as session:
            # Получение информации о канале
            channel = await session.execute(
                select(Group).where(Group.id == channel_id)
            )
            channel = channel.scalar_one_or_none()
            
            if not channel:
                await call.answer("⚠️ Канал не найден.")
                return

            # Обновление текущего чата пользователя
            await update_user_current_chat(user_id, channel.chat_id)

            # Создание клавиатуры
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Создать пост")],
                    [KeyboardButton(text="Контент план"), KeyboardButton(text="История публикаций")],
                    [KeyboardButton(text="Таблицы"), KeyboardButton(text="Настройки")],
                    [KeyboardButton(text="Сменить группу")]
                ],
                resize_keyboard=True
            )

            await call.message.answer(
                f"✅ Канал \"{channel.title}\" выбран!",
                reply_markup=keyboard
            )
            await call.answer()

    except Exception as e:
        logger.error(f"Error in process_channel_selection: {e}")
        await call.answer("⚠️ Ошибка при выборе канала.")

@router.message(Command('channels'))
async def cmd_channels(message: Message):
    """Обработка команды /channels"""
    try:
        keyboard = await create_channels_keyboard(message.from_user.id)
        await message.answer(
            "📝 <b>Ваши каналы и группы</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in cmd_channels: {e}")
        await message.answer("⚠️ Ошибка при получении списка каналов.")

@router.message(F.text == "Сменить группу")
async def change_group(message: Message):
    """Обработка кнопки смены группы"""
    await cmd_channels(message)
