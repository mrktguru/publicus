# handlers/channels.py
import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

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

@router.callback_query(lambda c: c.data == "add_channel")
async def add_channel_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик inline-кнопки для добавления канала"""
    await call.message.edit_text(
        "📌 Что вы хотите добавить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📣 Канал", callback_data="add_channel_type")],
            [InlineKeyboardButton(text="👥 Группу", callback_data="add_group_type")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_channels")]
        ])
    )

@router.callback_query(lambda c: c.data == "back_to_channels")
async def back_to_channels(call: CallbackQuery):
    """Возврат к списку каналов"""
    user_id = call.from_user.id
    try:
        keyboard = await create_channels_keyboard(user_id)
        await call.message.edit_text(
            "📝 <b>Выберите канал или группу для работы</b>\n\n"
            "Выберите одну из подключенных групп/каналов или добавьте новую.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in back_to_channels: {e}")
        await call.answer("Произошла ошибка. Пожалуйста, попробуйте снова.")

@router.callback_query(lambda c: c.data == "add_channel_type")
async def process_add_channel(call: CallbackQuery, state: FSMContext):
    """Обработчик для добавления канала"""
    await state.update_data(adding_type="channel")
    await call.message.edit_text(
        "📣 <b>Добавление нового канала</b>\n\n"
        "Для добавления канала выполните следующие шаги:\n\n"
        "1) Добавьте бота (@your_bot_username) администратором в канал\n"
        "2) Убедитесь, что у бота есть права на публикацию сообщений\n"
        "3) Перешлите любое сообщение из канала в этот чат\n"
        "<b>ИЛИ</b>\n"
        "Отправьте @username канала (если он публичный)",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_add_select")]
        ])
    )
    await state.set_state(ChannelStates.waiting_for_channel_message)
@router.callback_query(lambda c: c.data == "add_group_type")
async def process_add_group(call: CallbackQuery, state: FSMContext):
    """Обработчик для добавления группы"""
    await state.update_data(adding_type="group")
    await call.message.edit_text(
        "👥 <b>Добавление новой группы</b>\n\n"
        "Для добавления группы выполните следующие шаги:\n\n"
        "1) Добавьте бота (@your_bot_username) в группу\n"
        "2) Назначьте бота администратором с правами на публикацию сообщений\n"
        "3) Отправьте команду /connect в группе",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_add_select")]
        ])
    )
    await state.set_state(ChannelStates.waiting_for_group_command)

@router.callback_query(lambda c: c.data == "back_to_add_select")
async def back_to_add_select(call: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа добавления: канал или группа"""
    await call.message.edit_text(
        "📌 Что вы хотите добавить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📣 Канал", callback_data="add_channel_type")],
            [InlineKeyboardButton(text="👥 Группу", callback_data="add_group_type")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_channels")]
        ])
    )
    await state.clear()

@router.message(ChannelStates.waiting_for_channel_message)
async def process_channel_message(message: Message, state: FSMContext):
    """Обработка пересланного сообщения из канала"""
    user_id = message.from_user.id
    
    # Если пользователь отправил @username канала
    if message.text and message.text.startswith('@'):
        channel_username = message.text.strip()
        await state.update_data(channel_username=channel_username)
        await message.answer(
            f"🔄 Обрабатываю канал {channel_username}...\n\n"
            f"Пожалуйста, введите удобное название для этого канала (для отображения в боте):"
        )
        await state.set_state(ChannelStates.waiting_for_display_name)
        return
    # Если пользователь переслал сообщение из канала
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        channel_id = message.forward_from_chat.id
        channel_title = message.forward_from_chat.title
        channel_username = message.forward_from_chat.username
        
        try:
            async with AsyncSessionLocal() as session:
                # Проверяем, зарегистрирован ли уже этот канал
                existing_group_q = select(Group).filter(Group.chat_id == channel_id)
                existing_group_result = await session.execute(existing_group_q)
                existing_group = existing_group_result.scalar_one_or_none()
                
                if existing_group:
                    # Канал уже добавлен, проверяем, принадлежит ли он этому пользователю
                    if existing_group.added_by == user_id:
                        await message.answer(
                            f"⚠️ Этот канал уже добавлен вами ранее: {existing_group.title}"
                        )
                    else:
                        await message.answer(
                            f"⚠️ Этот канал уже добавлен другим пользователем."
                        )
                    await state.clear()
                    return
                
                # Добавляем канал в базу данных
                new_group = Group(
                    chat_id=channel_id,
                    title=channel_title,
                    username=channel_username,
                    display_name=channel_title,  # По умолчанию используем оригинальное название
                    type="channel",
                    added_by=user_id
                )
                
                session.add(new_group)
                await session.commit()
                
                # Обновляем текущий выбранный канал пользователя
                user_q = select(User).filter(User.user_id == user_id)
                user_result = await session.execute(user_q)
                user = user_result.scalar_one_or_none()
                
                if user:
                    user.current_chat_id = channel_id
                    await session.commit()
                
                # Уведомляем об успешном добавлении
                await message.answer(
                    f"✅ Канал \"{channel_title}\" успешно добавлен!\n\n"
                    f"Теперь вы можете создавать и публиковать контент для этого канала."
                )
                
                # Показываем список каналов для выбора
                keyboard = await create_channels_keyboard(user_id)
                await message.answer(
                    "📝 <b>Выберите канал или группу для работы</b>",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                
                # Очищаем состояние
                await state.clear()
                
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            await message.answer("⚠️ Произошла ошибка при добавлении канала. Пожалуйста, попробуйте позже.")
            await state.clear()
    else:
        # Если сообщение не переслано из канала
        await message.answer(
            "⚠️ Это не пересланное сообщение из канала. Пожалуйста, перешлите сообщение из канала "
            "или отправьте @username публичного канала."
        )
@router.message(ChannelStates.waiting_for_display_name)
async def process_display_name(message: Message, state: FSMContext):
    """Обработка ввода пользовательского имени для канала"""
    user_id = message.from_user.id
    display_name = message.text.strip()
    
    # Получаем данные из состояния
    user_data = await state.get_data()
    channel_username = user_data.get("channel_username")
    
    if not display_name:
        await message.answer("⚠️ Название не может быть пустым. Пожалуйста, введите название:")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, не добавлен ли уже канал с таким username
            existing_group_q = select(Group).filter(Group.username == channel_username.lstrip('@'))
            existing_group_result = await session.execute(existing_group_q)
            existing_group = existing_group_result.scalar_one_or_none()
            
            if existing_group:
                # Канал уже добавлен
                await message.answer(
                    f"⚠️ Канал {channel_username} уже добавлен в систему."
                )
                await state.clear()
                return
            
            # Добавляем канал в базу данных
            new_group = Group(
                chat_id=0,  # Временно, будет обновлено позже
                title=display_name,
                username=channel_username.lstrip('@'),
                display_name=display_name,
                type="channel",
                added_by=user_id
            )
            
            session.add(new_group)
            await session.commit()
            
            # Обновляем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if user:
                user.current_chat_id = new_group.id  # Используем ID из базы данных
                await session.commit()
            
            await message.answer(
                f"✅ Канал {channel_username} успешно добавлен как \"{display_name}\"!\n\n"
                f"⚠️ <b>Важно:</b> убедитесь, что бот добавлен в этот канал как администратор "
                f"с правами на публикацию сообщений.",
                parse_mode="HTML"
            )
            
            # Показываем список каналов для выбора
            keyboard = await create_channels_keyboard(user_id)
            await message.answer(
                "📝 <b>Выберите канал или группу для работы</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # Очищаем состояние
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error adding channel by username: {e}")
        await message.answer("⚠️ Произошла ошибка при добавлении канала. Пожалуйста, попробуйте позже.")
        await state.clear()
@router.message(Command('connect'))
async def connect_group(message: Message):
    """Обработка команды /connect в группе"""
    # Проверяем, что команда отправлена в группе
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer(
            "⚠️ Эта команда может быть использована только в группах.\n\n"
            "Чтобы подключить бота к группе, добавьте его в группу и отправьте там команду /connect"
        )
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_title = message.chat.title
    
    # Проверяем права бота в группе
    try:
        chat_member = await message.bot.get_chat_member(chat_id, message.bot.id)
        
        # Проверяем, что бот - администратор с нужными правами
        if not chat_member.status == "administrator":
            await message.answer(
                "⚠️ Для работы бот должен быть администратором группы.\n\n"
                "Пожалуйста, назначьте бота администратором и повторите команду."
            )
            return
        
        # Проверяем, что у бота есть права на отправку сообщений
        if not chat_member.can_post_messages:
            await message.answer(
                "⚠️ У бота нет прав на отправку сообщений в этой группе.\n\n"
                "Пожалуйста, назначьте боту соответствующие права и повторите команду."
            )
            return
        
        # Проверяем права пользователя, отправившего команду
        user_chat_member = await message.bot.get_chat_member(chat_id, user_id)
        if user_chat_member.status not in ["creator", "administrator"]:
            await message.answer(
                "⚠️ Только администраторы группы могут использовать эту команду."
            )
            return
        async with AsyncSessionLocal() as session:
            # Проверяем, зарегистрирована ли уже эта группа
            existing_group_q = select(Group).filter(Group.chat_id == chat_id)
            existing_group_result = await session.execute(existing_group_q)
            existing_group = existing_group_result.scalar_one_or_none()
            
            if existing_group:
                # Группа уже добавлена, проверяем, принадлежит ли она этому пользователю
                if existing_group.added_by == user_id:
                    await message.answer(
                        f"⚠️ Эта группа уже подключена к боту."
                    )
                else:
                    await message.answer(
                        f"⚠️ Эта группа уже подключена к боту другим пользователем."
                    )
                return
            
            # Добавляем группу в базу данных
            new_group = Group(
                chat_id=chat_id,
                title=chat_title,
                username=message.chat.username,
                display_name=chat_title,  # По умолчанию используем оригинальное название
                type="group",
                added_by=user_id
            )
            
            session.add(new_group)
            await session.commit()
            
            # Обновляем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if user:
                user.current_chat_id = chat_id
                await session.commit()
            
            # Отправляем подтверждение в группу
            await message.answer(
                f"✅ Группа \"{chat_title}\" успешно подключена к боту!\n\n"
                f"Теперь вы можете создавать и публиковать контент для этой группы через личные сообщения с ботом."
            )
            
            # Отправляем сообщение в личку пользователю
            await message.bot.send_message(
                user_id,
                f"✅ Группа \"{chat_title}\" успешно подключена!\n\n"
                f"Теперь вы можете создавать и публиковать контент для этой группы."
            )
            
    except Exception as e:
        logger.error(f"Error connecting group: {e}")
        await message.answer("⚠️ Произошла ошибка при подключении группы. Пожалуйста, попробуйте позже.")
@router.callback_query(lambda c: c.data.startswith("select_channel_"))
async def process_channel_selection(call: CallbackQuery, state: FSMContext):
    """Обработка выбора канала/группы"""
    user_id = call.from_user.id
    channel_id = int(call.data.split("_")[2])
    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем информацию о канале
            channel_q = select(Group).filter(Group.id == channel_id)
            channel_result = await session.execute(channel_q)
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                await call.answer("⚠️ Выбранный канал не найден.")
                return
            
            # Обновляем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if user:
                user.current_chat_id = channel.chat_id
                await session.commit()
            
            # Создаем клавиатуру с основными действиями
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Создать пост")],
                    [KeyboardButton(text="Контент план"), KeyboardButton(text="История публикаций")],
                    [KeyboardButton(text="Таблицы"), KeyboardButton(text="Настройки")],
                    [KeyboardButton(text="Сменить группу")]
                ],
                resize_keyboard=True,
                is_persistent=True
            )
            
            # Отправляем уведомление о выборе канала и показываем меню
            await call.message.edit_text(
                f"✅ Канал \"{channel.title}\" выбран!\n\n"
                f"Выберите действие:"
            )
            
            # Отправляем новое сообщение с клавиатурой
            await call.message.answer(
                f"Канал \"{channel.title}\" выбран!",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error selecting channel: {e}")
        await call.answer("⚠️ Произошла ошибка при выборе канала. Пожалуйста, попробуйте позже.")
@router.message(lambda m: m.text == "Сменить группу")
async def change_group(message: Message):
    """Обработка кнопки 'Сменить группу' из основного меню"""
    user_id = message.from_user.id
    
    try:
        # Создаем клавиатуру с каналами пользователя
        keyboard = await create_channels_keyboard(user_id)
        
        await message.answer(
            "📝 <b>Выберите канал или группу для работы</b>\n\n"
            "Выберите одну из подключенных групп/каналов или добавьте новую.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in change_group handler: {e}")
        await message.answer("⚠️ Произошла ошибка при получении списка каналов. Пожалуйста, попробуйте позже.")

@router.message(Command('channels'))
async def cmd_channels(message: Message):
    """Обработка команды /channels для просмотра списка каналов"""
    user_id = message.from_user.id
    
    try:
        # Создаем клавиатуру с каналами пользователя
        keyboard = await create_channels_keyboard(user_id)
        
        await message.answer(
            "📝 <b>Выберите канал или группу для работы</b>\n\n"
            "Выберите одну из подключенных групп/каналов или добавьте новую.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in cmd_channels handler: {e}")
        await message.answer("⚠️ Произошла ошибка при получении списка каналов. Пожалуйста, попробуйте позже.")
