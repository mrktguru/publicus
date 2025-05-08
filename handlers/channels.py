# handlers/channels.py
import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, text  # Добавьте импорт text


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
        channel_username_value = message.forward_from_chat.username
        
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
                
                # Используем прямой SQL запрос вместо ORM
                # ИСПРАВЛЕННЫЙ КОД: Используем text() для SQL запроса
                sql = text("""
                INSERT INTO groups (chat_id, title, added_by, date_added) 
                VALUES (:chat_id, :title, :added_by, CURRENT_TIMESTAMP)
                """)
                await session.execute(sql, {
                    "chat_id": channel_id,
                    "title": channel_title,
                    "added_by": user_id
                })
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
            username_without_at = channel_username.lstrip('@') if channel_username else None
            
            # Используем прямой SQL запрос вместо ORM
           # ИСПРАВЛЕННЫЙ КОД: Используем text() для SQL запроса
            sql = text("""
            INSERT INTO groups (chat_id, title, added_by, date_added) 
            VALUES (0, :title, :added_by, CURRENT_TIMESTAMP)
            """)
            result = await session.execute(sql, {
                "title": display_name,
                "added_by": user_id
            })
            await session.commit()
            
            # Получаем ID только что созданной группы
            group_id_query = text("""
            SELECT id FROM groups 
            WHERE chat_id = 0 AND title = :title AND added_by = :added_by
            ORDER BY id DESC LIMIT 1
            """)
            result = await session.execute(group_id_query, {
                "title": display_name,
                "added_by": user_id
            })
            group_id = result.scalar_one_or_none()
            
            # Обновляем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if user and group_id:
                user.current_chat_id = group_id
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
            
            # Используем прямой SQL запрос вместо ORM
            # ИСПРАВЛЕННЫЙ КОД: Используем text() для SQL запроса
            sql = text("""
            INSERT INTO groups (chat_id, title, added_by, date_added) 
            VALUES (:chat_id, :title, :added_by, CURRENT_TIMESTAMP)
            """)
            await session.execute(sql, {
                "chat_id": chat_id,
                "title": chat_title,
                "added_by": user_id
            })
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

# Обработчики выбора канала/группы
@router.callback_query(lambda c: c.data and c.data.startswith("select_channel_"))
async def process_channel_selection(call: CallbackQuery, state: FSMContext):
    """Обработка выбора канала/группы"""
    user_id = call.from_user.id
    
    try:
        # Логирование для отладки
        logger.info(f"Select channel callback received: {call.data}")
        
        # Извлекаем ID канала из данных коллбэка
        channel_id = int(call.data.split("_")[2])
        logger.info(f"Extracted channel_id: {channel_id}")
        
        async with AsyncSessionLocal() as session:
            # Получаем информацию о канале
            channel_q = select(Group).filter(Group.id == channel_id)
            channel_result = await session.execute(channel_q)
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                logger.error(f"Channel with id {channel_id} not found")
                await call.answer("⚠️ Выбранный канал не найден.")
                return
            
            logger.info(f"Found channel: {channel.title}, chat_id: {channel.chat_id}")
            
            # Обновляем текущий выбранный канал пользователя
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if user:
                user.current_chat_id = channel.chat_id
                await session.commit()
                logger.info(f"Updated user current_chat_id to {channel.chat_id}")
            
            # Сохраняем данные о выбранном канале в состоянии
            await state.update_data(
                chat_id=channel.chat_id,
                group_id=channel.id,  # Добавляем ID группы в состояние
                current_channel_title=channel.title
            )
            logger.info(f"Saved group data to state: id={channel.id}, title={channel.title}, chat_id={channel.chat_id}")
            
            # Создаем клавиатуру с основными действиями
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Создать пост")],
                    [KeyboardButton(text="Контент план (Очередь публикаций)")],
                    [KeyboardButton(text="История публикаций")],
                    [KeyboardButton(text="Таблицы Google Sheets")],
                    [KeyboardButton(text="↩️ Назад")]
                ],
                resize_keyboard=True,
                is_persistent=True
            )
            
            # Отправляем уведомление о выборе канала
            try:
                await call.message.edit_text(
                    f"✅ Канал \"{channel.title}\" выбран!\n\n"
                    f"Выберите действие:"
                )
            except Exception as edit_error:
                logger.error(f"Error editing message: {edit_error}")
                # Если не удалось отредактировать сообщение, отправляем новое
                await call.message.answer(
                    f"✅ Канал \"{channel.title}\" выбран!\n\n"
                    f"Выберите действие:"
                )
            
            # Отправляем новое сообщение с клавиатурой
            await call.message.answer(
                f"Работаем с каналом: \"{channel.title}\"",
                reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Создать пост", callback_data="create_post")],
                    [InlineKeyboardButton(text="Контент план", callback_data="show_schedule")],
                    [InlineKeyboardButton(text="История публикаций", callback_data="post_history")],
                    [InlineKeyboardButton(text="Таблицы Google Sheets", callback_data="open_sheets_menu")],
                    [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
                ])
            )
            # Отвечаем на коллбэк, чтобы убрать "часики" на кнопке
            await call.answer()
            
    except Exception as e:
        logger.error(f"Error selecting channel: {e}")
        await call.answer("⚠️ Произошла ошибка при выборе канала. Пожалуйста, попробуйте позже.")
        # Отправляем сообщение в чат с описанием ошибки
        await call.message.answer(f"Произошла ошибка: {str(e)}")


# Обработчики для кнопок основного меню
@router.message(lambda m: m.text == "Создать пост")
async def create_post_handler(message: Message, state: FSMContext):
    """Обработчик кнопки 'Создать пост'"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Создаем inline клавиатуру для выбора типа создания поста
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Написать вручную", callback_data="post_manual")],
        [InlineKeyboardButton(text="🤖 Сгенерировать с помощью ИИ", callback_data="post_auto")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(
        f"📝 <b>Создание поста в канале \"{current_channel}\"</b>\n\n"
        f"Выберите способ создания поста:",
        parse_mode="HTML",
        reply_markup=markup
    )

@router.message(lambda m: m.text == "Контент план (Очередь публикаций)" or m.text == "Контент план")
async def content_plan_handler(message: Message, state: FSMContext):
    """Обработчик кнопки 'Контент план'"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Здесь должен быть код для отображения контент-плана
    await message.answer(
        f"📅 <b>Контент план канала \"{current_channel}\"</b>\n\n"
        f"Здесь будут отображаться запланированные публикации.",
        parse_mode="HTML"
    )

@router.message(lambda m: m.text == "История публикаций")
async def history_handler(message: Message, state: FSMContext):
    """Обработчик кнопки 'История публикаций'"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Здесь должен быть код для отображения истории публикаций
    await message.answer(
        f"📋 <b>История публикаций канала \"{current_channel}\"</b>\n\n"
        f"Здесь будет отображаться история опубликованных постов.",
        parse_mode="HTML"
    )
# ОБРАБОТЧИК Таблицы Google Sheets для обычных кнопок и для инлайн НАЧАЛО
 
@router.message(lambda m: m.text == "Таблицы Google Sheets" or m.text == "Таблицы")
async def sheets_handler(message: Message, state: FSMContext):
    """Обработчик кнопки 'Таблицы Google Sheets'"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Создаем inline клавиатуру для действий с таблицами
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")],
        [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sheet_sync")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(
        f"📊 <b>Интеграция с Google Sheets для канала \"{current_channel}\"</b>\n\n"
        f"Выберите действие с таблицами:",
        parse_mode="HTML",
        reply_markup=markup
    )

@router.callback_query(F.data == "open_sheets_menu")  # Новый обработчик
async def sheets_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Подключить таблицу", callback_data="sheet_connect")],
        [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="sheet_sync")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.answer(
        f"📊 <b>Интеграция с Google Sheets для канала \"{current_channel}\"</b>\n\n"
        f"Выберите действие с таблицами:",
        parse_mode="HTML",
        reply_markup=markup
    )
    await callback.answer()

# ОБРАБОТЧИК Таблицы Google Sheets для обычных кнопок и для инлайн КОНЕЦ



@router.message(lambda m: m.text == "↩️ Назад" or m.text == "🔙 Сменить группу" or m.text == "Сменить группу")
async def back_to_channels_list(message: Message, state: FSMContext):
    """Обработчик кнопки 'Назад'/'Сменить группу'"""
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
        logger.error(f"Error in back_to_channels_list handler: {e}")
        await message.answer("⚠️ Произошла ошибка при получении списка каналов. Пожалуйста, попробуйте позже.")

# Обработчики для inline кнопок
@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_menu(call: CallbackQuery, state: FSMContext):
    """Возврат к основному меню"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    await call.message.edit_text(
        f"Вы работаете с каналом \"{current_channel}\"\n\n"
        f"Выберите действие в меню ниже."
    )
    
    await call.answer()

# обработчик кнопки НАСТРОЙКИ
@router.message(lambda m: m.text == "Настройки" or m.text == "⚙️ Настройки")
async def settings_handler(message: Message, state: FSMContext):
    """Обработчик кнопки 'Настройки'"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Создаем inline клавиатуру для настроек
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖊️ Изменить название", callback_data="settings_rename")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(
        f"⚙️ <b>Настройки канала \"{current_channel}\"</b>\n\n"
        f"Выберите настройки для изменения:",
        parse_mode="HTML",
        reply_markup=markup
    )

# обработчик выбора ручного создания поста
@router.callback_query(lambda c: c.data == "post_manual")
async def handle_post_manual(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора ручного создания поста"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    group_id = user_data.get("group_id")
    chat_id = user_data.get("chat_id")
    
    # Проверяем, выбран ли канал
    if not group_id or not chat_id:
        await call.message.edit_text("⚠️ Сначала выберите канал для работы")
        await call.answer()
        return
    
    # Журналирование для отладки
    logger.info(f"Starting manual post creation for channel: {current_channel} (id={group_id}, chat_id={chat_id})")
    
    # Просим пользователя ввести текст поста
    await call.message.edit_text(
        f"📝 <b>Создание поста вручную для канала \"{current_channel}\"</b>\n\n"
        f"Введите текст вашего поста. Вы можете использовать стандартное форматирование Telegram:\n"
        f"*жирный* _курсив_ `код` [ссылка](URL)",
        parse_mode="HTML"
    )
    
    # Добавляем кнопку отмены
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")]
    ])
    
    await call.message.answer(
        "Для отмены создания поста нажмите кнопку ниже:",
        reply_markup=markup
    )
    
    # Устанавливаем состояние ожидания текста поста и передаем group_id
    # Для этого используем состояние из states/post_states.py
    from states.post_states import ManualPostStates
    await state.set_state(ManualPostStates.waiting_for_content)
    
    # Сохраняем данные о группе в состоянии
    await state.update_data(
        group_id=group_id,
        chat_id=chat_id,
        current_channel_title=current_channel
    )
    
    await call.answer()


@router.callback_query(lambda c: c.data == "cancel_post")
async def cancel_post_creation(call: CallbackQuery, state: FSMContext):
    """Отмена создания поста"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    await call.message.edit_text(
        f"❌ Создание поста для канала \"{current_channel}\" отменено."
    )
    
    # Возвращаемся к основному меню
    await back_to_main(call, state)

@router.callback_query(lambda c: c.data == "back_to_create_options")
async def back_to_create_options(call: CallbackQuery, state: FSMContext):
    """Возврат к выбору способа создания поста"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Создаем inline клавиатуру для выбора типа создания поста
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Написать вручную", callback_data="post_manual")],
        [InlineKeyboardButton(text="🤖 Сгенерировать с помощью ИИ", callback_data="post_auto")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    
    await call.message.edit_text(
        f"📝 <b>Создание поста в канале \"{current_channel}\"</b>\n\n"
        f"Выберите способ создания поста:",
        parse_mode="HTML",
        reply_markup=markup
    )


