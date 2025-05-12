from typing import Union  # Добавьте этот импорт
from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardRemove,
    InputMediaPhoto,
)
from aiogram.fsm.context import FSMContext
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from database.db import AsyncSessionLocal
from database.models import Post, Group
from states.post_states import ManualPostStates
# Меняем импорт клавиатуры
from utils.keyboards import create_main_keyboard

router = Router()
logger = logging.getLogger(__name__)


async def _start_manual_process(source: Union[Message, CallbackQuery], state: FSMContext):
    """Общая функция для запуска ручного создания поста"""
    data = await state.get_data()
    
    if not data.get("group_id"):
        if isinstance(source, CallbackQuery):
            await source.message.answer("❌ Сначала выберите группу через /start")
            await source.answer()
        else:
            await source.answer("❌ Сначала выберите группу через /start")
        return
        
    try:
        async with AsyncSessionLocal() as session:
            group = await session.get(Group, data["group_id"])
            if not group:
                if isinstance(source, CallbackQuery):
                    await source.message.answer("❌ Группа не найдена")
                    await source.answer()
                else:
                    await source.answer("❌ Группа не найдена")
                return
                
            await state.update_data(group_title=group.title)
    except Exception as e:
        logger.error(f"Error: {e}")
        if isinstance(source, CallbackQuery):
            await source.message.answer("❌ Ошибка при проверке группы")
            await source.answer()
        else:
            await source.answer("❌ Ошибка при проверке группы")
        return
    
    await state.update_data(text=None, media_file_id=None)
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_creation")],
        ]
    )
    
    # Исправленная часть: всегда используем отправку нового сообщения
    if isinstance(source, CallbackQuery):
        await source.message.answer(
            "✏️ Начинаем создание поста. Отправьте текст:",
            reply_markup=kb
        )
        await source.answer()  # Скрываем часики на кнопке
    else:
        await source.answer(
            "✏️ Начинаем создание поста. Отправьте текст:",
            reply_markup=kb
        )
    
    # Добавляем эту строку для установки состояния
    await state.set_state(ManualPostStates.waiting_for_content)

# Оригинальный обработчик
@router.message(F.text.startswith("✏️ Создать пост"))
async def start_manual(message: Message, state: FSMContext):
    await _start_manual_process(message, state)

# Новый обработчик для инлайн-кнопки "Создать пост"
@router.callback_query(F.data == "post:create_manual")
async def handle_create_manual_choice(call: CallbackQuery, state: FSMContext):
    """Показывает меню выбора способа создания поста при нажатии на инлайн-кнопку"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Создаем inline клавиатуру для выбора типа создания поста
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Написать вручную", callback_data="post_manual")],
        [InlineKeyboardButton(text="🤖 Сгенерировать с помощью ИИ", callback_data="post_auto")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    
    await call.message.answer(
        f"📝 <b>Создание поста в канале \"{current_channel}\"</b>\n\n"
        f"Выберите способ создания поста:",
        parse_mode="HTML",
        reply_markup=markup
    )
    await call.answer()

# Обработчики для кнопок выбора способа создания поста
@router.callback_query(F.data == "post_manual")
async def handle_post_manual_start(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора ручного создания поста"""
    await _start_manual_process(call, state)

@router.callback_query(F.data == "post_auto")
async def handle_post_auto_start(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора создания поста с помощью ИИ"""
    # Тут должна быть логика для создания поста с помощью ИИ
    # Например, переход к форме запроса темы для генерации и т.д.
    await call.message.answer("🤖 Генерация поста с помощью ИИ. Функция в разработке.")
    await call.answer()



# ── обработка текста ───────────────────────────────────────────
@router.message(ManualPostStates.waiting_for_content, F.text)
async def handle_text(message: Message, state: FSMContext):
    logger.info("Handling text in waiting_for_content state")
    data = await state.get_data()
    text = message.text
    media_file_id = data.get("media_file_id")
    
    # Если уже есть текст, но нет фото - предложим заменить текст или добавить фото
    if data.get("text") and not media_file_id:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo")],
                [InlineKeyboardButton(text="⏱️ Далее (планирование)", callback_data="proceed_to_planning")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")],
            ]
        )
        await state.update_data(text=text)
        await message.answer(
            f"✅ Текст обновлен:\n\n{text[:200]}{'...' if len(text) > 200 else ''}\n\n"
            "Хотите добавить фотографию или перейти к планированию публикации?",
            reply_markup=kb
        )
    
    # Если уже есть фото, но пришел новый текст - обновляем текст и показываем превью
    elif media_file_id:
        await state.update_data(text=text)
        
        # Отправляем предпросмотр публикации
        try:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Опубликовать сразу", callback_data="manual_publish_now")],
                    [InlineKeyboardButton(text="⏰ Запланировать публикацию", callback_data="manual_schedule")],
                    [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
                    [InlineKeyboardButton(text="🖼️ Изменить фото", callback_data="edit_photo")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")],
                ]
            )
            
            # 1. Отправляем заголовок предпросмотра
            await message.answer("📝 Предпросмотр поста:")
            
            # 2. Отправляем чистое фото с подписью
            await message.answer_photo(
                photo=media_file_id,
                caption=text
            )
            
            # 3. Отправляем кнопки действий отдельным сообщением
            await message.answer(
                "Выберите действие с этим постом:",
                reply_markup=kb
            )
            
            await state.set_state(ManualPostStates.waiting_for_choice)
        except Exception as e:
            logger.error(f"Error showing post preview: {e}")
            await message.answer(f"❌ Произошла ошибка при показе предпросмотра. Пожалуйста, попробуйте снова.")
    
    # Если ни текста, ни фото еще нет - сохраняем текст и предлагаем добавить фото
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo")],
                [InlineKeyboardButton(text="⏱️ Далее (планирование)", callback_data="proceed_to_planning")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")],
            ]
        )
        await state.update_data(text=text)
        await message.answer(
            f"✅ Текст сохранен:\n\n{text[:200]}{'...' if len(text) > 200 else ''}\n\n"
            "Хотите добавить фотографию или перейти к планированию публикации?",
            reply_markup=kb
        )

# ── обработка изображения ───────────────────────────────────────
@router.message(ManualPostStates.waiting_for_content, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    logger.info("Handling photo in waiting_for_content state")
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    
    # Если уже был сохранен текст, используем его вместе с фото
    saved_text = data.get("text", "")
    if saved_text and not caption:
        text_to_save = saved_text
    else:
        text_to_save = caption
    
    # Сохраняем данные
    await state.update_data(text=text_to_save, media_file_id=file_id)
    
    # Кнопки для действий с постом
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Опубликовать сразу", callback_data="manual_publish_now")],
            [InlineKeyboardButton(text="⏰ Запланировать публикацию", callback_data="manual_schedule")],
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton(text="🖼️ Изменить фото", callback_data="edit_photo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")],
        ]
    )
    
    # 1. Сначала отправляем сообщение о получении фото
    await message.answer("✅ Фото получено!")
    
    # 2. Отправляем заголовок предпросмотра
    await message.answer("📝 Предпросмотр поста:")
    
    # 3. Отправляем чистое фото с подписью (без дополнительных надписей)
    await message.answer_photo(
        photo=file_id,
        caption=text_to_save
    )
    
    # 4. Отправляем кнопки действий отдельным сообщением
    await message.answer(
        "Выберите действие с этим постом:",
        reply_markup=kb
    )
    
    await state.set_state(ManualPostStates.waiting_for_choice)

# ── обработка callback-кнопок во время ввода контента ────────────
@router.callback_query(F.data == "add_photo")
async def request_photo(call: CallbackQuery, state: FSMContext):
    logger.info("User requested to add photo")
    await call.message.edit_text(
        "📸 Отправьте фотографию.\nЕсли хотите заменить текст, добавьте подпись к фото."
    )
    await state.set_state(ManualPostStates.waiting_for_content)
    await call.answer()

@router.callback_query(F.data == "proceed_to_planning")
async def show_publishing_options(call: CallbackQuery, state: FSMContext):
    logger.info("User requested to proceed to planning")
    data = await state.get_data()
    text = data.get("text", "")
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Опубликовать сразу", callback_data="manual_publish_now")],
            [InlineKeyboardButton(text="⏰ Запланировать публикацию", callback_data="manual_schedule")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")],
        ]
    )
    
    # Показываем заголовок предпросмотра
    await call.message.edit_text("📝 Предпросмотр поста:")
    
    # Затем отправляем сам текст поста
    await call.message.answer(text)
    
    # И кнопки действий
    await call.message.answer(
        "Выберите действие с этим постом:",
        reply_markup=kb
    )
    
    await state.set_state(ManualPostStates.waiting_for_choice)
    await call.answer()

@router.callback_query(F.data == "edit_text")
async def edit_text_request(call: CallbackQuery, state: FSMContext):
    logger.info("User requested to edit text")
    await call.message.edit_text(
        "✏️ Отправьте новый текст для поста:"
    )
    await state.set_state(ManualPostStates.waiting_for_content)
    await call.answer()

@router.callback_query(F.data == "edit_photo")
async def edit_photo_request(call: CallbackQuery, state: FSMContext):
    logger.info("User requested to edit photo")
    await call.message.edit_text(
        "🖼️ Отправьте новую фотографию для поста.\nЕсли хотите заменить текст, добавьте подпись к фото."
    )
    # Сохраним только текст, удалим старое фото
    data = await state.get_data()
    await state.update_data(text=data.get("text"), media_file_id=None)
    await state.set_state(ManualPostStates.waiting_for_content)
    await call.answer()

@router.callback_query(F.data == "cancel_creation")
async def cancel_creation(call: CallbackQuery, state: FSMContext):
    logger.info("User cancelled post creation")
    # Сохраняем данные о группе
    data = await state.get_data()
    group_id = data.get("group_id")
    group_title = data.get("group_title")
    
    # Очищаем состояние, но сохраняем информацию о группе
    await state.clear()
    await state.set_data({"group_id": group_id, "group_title": group_title})
    
    await call.message.edit_text("❌ Создание поста отменено.")
    
    # Используем новое меню вместо старого
    main_kb = await create_main_keyboard()
    await call.message.answer("Выберите действие:", reply_markup=main_kb)
    await call.answer()

# ── публикация «сейчас» ────────────────────────────────────────
@router.callback_query(F.data == "manual_publish_now")
async def publish_now(call: CallbackQuery, state: FSMContext):
    """Публикация поста сейчас."""
    logger.info("Publishing post now")
    data = await state.get_data()
    logger.info(f"Publishing post now with data: {data}")
    
    text = data.get("text", "")
    media_file_id = data.get("media_file_id")
    group_pk = data.get("group_id")  # Используем group_id из состояния

    if not group_pk:
        await call.message.edit_text("❌ Ошибка: группа не выбрана. Пожалуйста, выберите группу через /start")
        await state.clear()
        return

    # 1) Получаем chat_id
    try:
        async with AsyncSessionLocal() as session:
            group = await session.get(Group, group_pk)
            if not group:
                await call.message.edit_text("❌ Ошибка: выбранная группа не найдена.")
                await state.clear()
                return
            chat_id = group.chat_id
            logger.info(f"Found group: {group.title}, chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error getting group: {e}")
        await call.message.edit_text(f"❌ Ошибка при получении группы: {e}")
        await state.clear()
        return

    # 2) Проверяем содержимое
    if not text and not media_file_id:
        await call.message.edit_text("❌ Ошибка: нет текста или медиа для отправки.")
        await state.clear()
        return
    
    # Логируем перед отправкой
    logger.info(f"Attempting to send message to chat_id: {chat_id}")
    logger.info(f"Text: {text[:100]}...")
    logger.info(f"Media file ID: {media_file_id}")

    # 3) Отправляем в чат
    try:
        if media_file_id:
            result = await call.bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=text)
            logger.info(f"Photo message sent successfully: {result.message_id}")
        else:
            result = await call.bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Text message sent successfully: {result.message_id}")
    except Exception as e:
        logger.error(f"Error sending message to chat: {e}")
        await call.message.edit_text(f"❌ Ошибка отправки сообщения: {e}")
        await state.clear()
        return

    # 4) Сохраняем запись в БД
    now_msk = datetime.now(ZoneInfo("Europe/Moscow"))
    async with AsyncSessionLocal() as session:
        try:
            post = Post(
                chat_id=chat_id,
                text=text,
                media_file_id=media_file_id,
                publish_at=now_msk,
                created_by=call.from_user.id,
                status="sent",
                published=True
            )
            session.add(post)
            await session.commit()
            logger.info(f"Post saved to database with ID {post.id}")
        except Exception as e:
            logger.error(f"Error saving post to database: {e}")
            # Продолжаем выполнение, так как сообщение уже отправлено

    # 5) Успех и возврат в главное меню
    await call.message.edit_text("✅ Пост опубликован!")
    
    # Сохраняем group_id и group_title для следующих операций
    await state.set_data({
        "group_id": group_pk, 
        "chat_id": chat_id,
        "current_channel_title": group.title
    })
    
    # Используем новое меню вместо старого
    main_kb = await create_main_keyboard()
    await call.message.answer("Выберите действие:", reply_markup=main_kb)
    await call.answer()

# ── запрос времени для планирования ───────────────────────────
@router.callback_query(F.data == "manual_schedule")
async def schedule_choice(call: CallbackQuery, state: FSMContext):
    logger.info("User requested post scheduling")
    # Сохраним данные состояния перед переходом
    data = await state.get_data()
    
    await call.message.edit_text(
        "📅 Введите дату и время публикации в формате ДД.MM.ГГГГ ЧЧ:ММ"
    )
    await state.set_state(ManualPostStates.waiting_for_datetime)
    await call.answer()

# ── ввод даты/времени ──────────────────────────────────────────
@router.message(ManualPostStates.waiting_for_datetime)
async def input_datetime(message: Message, state: FSMContext):
    logger.info(f"Processing date input: {message.text}")
    try:
        dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Moscow"))
    except ValueError:
        return await message.answer("⛔️ Неверный формат. Пожалуйста: ДД.MM.ГГГГ ЧЧ:ММ")

    # Получаем текущие данные состояния
    data = await state.get_data()
    # Добавляем время публикации к данным
    data["publish_at"] = dt
    await state.update_data(data)
    
    text = data.get("text", "")
    media_file_id = data.get("media_file_id")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="manual_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="manual_cancel")],
        ]
    )
    
    # Отправляем заголовок для предпросмотра
    await message.answer("📝 Предпросмотр запланированного поста:")
    
    # Если есть фото, показываем пост с фото
    if media_file_id:
        # Отправляем чистый пост с фото
        await message.answer_photo(
            photo=media_file_id,
            caption=text
        )
    else:
        # Если фото нет, показываем только текст
        await message.answer(text)
    
    # Отдельно показываем запланированное время
    await message.answer(
        f"🕒 Запланировано на: {dt:%d.%m.%Y %H:%M}\n\nПодтвердить?",
        reply_markup=kb
    )
    
    await state.set_state(ManualPostStates.waiting_for_confirm)

# ── подтверждение планирования ─────────────────────────────────
@router.callback_query(F.data == "manual_confirm")
async def confirm_manual(call: CallbackQuery, state: FSMContext):
    logger.info("Confirming scheduled post")
    data = await state.get_data()
    group_pk = data.get("group_id")
    media_file_id = data.get("media_file_id")
    text = data.get("text", "")

    if not group_pk:
        await call.message.edit_text("❌ Ошибка: группа не выбрана. Пожалуйста, выберите группу через /start")
        await state.clear()
        return

    async with AsyncSessionLocal() as session:
        group = await session.get(Group, group_pk)
        if not group:
            await call.message.edit_text("❌ Ошибка: выбранная группа не найдена.")
            await state.clear()
            return
            
        chat_id = group.chat_id
        post = Post(
            chat_id=chat_id,
            text=text,
            media_file_id=media_file_id,
            publish_at=data.get("publish_at"),
            created_by=call.from_user.id,
            status="approved",
        )
        session.add(post)
        await session.commit()

    await call.message.edit_text("✅ Пост запланирован!")
    
    # Сохраняем group_id и group_title для следующих операций
    await state.set_data({
        "group_id": group_pk, 
        "group_title": group.title,
        "current_channel_title": group.title
    })
    
    # Используем новое меню вместо старого
    main_kb = await create_main_keyboard()
    await call.message.answer("Выберите действие:", reply_markup=main_kb)
    await call.answer()

# ── отмена ─────────────────────────────────────────────────────
@router.callback_query(F.data == "manual_cancel")
async def cancel_manual(call: CallbackQuery, state: FSMContext):
    logger.info("Cancelling post scheduling")
    # Получаем текущие данные состояния
    data = await state.get_data()
    group_id = data.get("group_id")
    group_title = data.get("group_title")
    
    await call.message.edit_text("❌ Планирование отменено.")
    
    # Сохраняем group_id и group_title для следующих операций
    await state.set_data({
        "group_id": group_id, 
        "group_title": group_title,
        "current_channel_title": group_title
    })
    
    # Используем новое меню вместо старого
    main_kb = await create_main_keyboard()
    await call.message.answer("Выберите действие:", reply_markup=main_kb)
    await call.answer()
