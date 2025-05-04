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
from keyboards.main import main_menu_kb

router = Router()
logger = logging.getLogger(__name__)

# ── запуск сценария ────────────────────────────────────────────
@router.message(F.text.startswith("✏️ Создать пост"))
async def start_manual(message: Message, state: FSMContext):
    logger.info("Handler start_manual triggered with message: %s", message.text)
    data = await state.get_data()
    logger.info(f"Starting manual post with state data: {data}")
    
    if not data.get("group_id"):
        logger.warning(f"No group_id in state data: {data}")
        await message.answer("❌ Сначала выберите группу через /start")
        return
        
    # Проверим, действительно ли группа существует
    try:
        async with AsyncSessionLocal() as session:
            group = await session.get(Group, data["group_id"])
            if not group:
                logger.warning(f"Group with ID {data['group_id']} not found")
                await message.answer("❌ Выбранная группа не найдена. Пожалуйста, выберите группу снова через /start")
                return
            # Добавляем дополнительную информацию о группе в состояние
            await state.update_data(group_title=group.title)
            logger.info(f"Group found: {group.id} - {group.title}")
    except Exception as e:
        logger.error(f"Error checking group existence: {e}")
        await message.answer("❌ Произошла ошибка при проверке группы. Попробуйте выбрать группу снова через /start")
        return
    
    # Очищаем предыдущее состояние, если оно было
    await state.update_data(text=None, media_file_id=None)
    
    # Переходим к вводу текста поста и скрываем клавиатуру
    await state.set_state(ManualPostStates.waiting_for_content)
    await message.answer(
        "💬 Отправьте текст поста или фотографию с текстом (подписью).\n\n"
        "Вы можете:\n"
        "• Отправить только текст\n"
        "• Отправить фото с подписью\n"
        "• Отправить текст, а затем фото (я объединю их)",
        reply_markup=ReplyKeyboardRemove()
    )

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
            
            # Сначала отправляем превью публикации
            await message.answer_photo(
                photo=media_file_id,
                caption=f"📝 Предпросмотр поста:\n\n{text}",
            )
            
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
    
    # Показываем готовый пост с превью и кнопками действий
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Опубликовать сразу", callback_data="manual_publish_now")],
            [InlineKeyboardButton(text="⏰ Запланировать публикацию", callback_data="manual_schedule")],
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton(text="🖼️ Изменить фото", callback_data="edit_photo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")],
        ]
    )
    
    # Сначала отправляем сообщение о получении фото
    await message.answer("✅ Фото получено!")
    
    # Затем отправляем превью публикации
    await message.answer_photo(
        photo=file_id,
        caption=f"📝 Предпросмотр поста:\n\n{text_to_save}",
    )
    
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
    
    # Показываем текст поста
    await call.message.edit_text(
        f"📝 Предпросмотр текста:\n\n{text}\n\nВыберите действие:",
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
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
    await call.answer()

# ── публикация «сейчас» ────────────────────────────────────────
@router.callback_query(F.data == "manual_publish_now")
async def publish_now(call: CallbackQuery, state: FSMContext):
    logger.info("Publishing post now")
    data = await state.get_data()
    logger.info(f"Publishing post now with data: {data}")
    
    text = data.get("text", "")
    media_file_id = data.get("media_file_id")
    group_pk = data.get("group_id")

    if not group_pk:
        await call.message.edit_text("❌ Ошибка: группа не выбрана. Пожалуйста, выберите группу через /start")
        await state.clear()
        return

    # 1) Получаем chat_id
    async with AsyncSessionLocal() as session:
        group = await session.get(Group, group_pk)
        if not group:
            await call.message.edit_text("❌ Ошибка: выбранная группа не найдена.")
            await state.clear()
            return
        chat_id = group.chat_id

    # 2) Проверяем содержимое
    if not text and not media_file_id:
        await call.message.edit_text("❌ Ошибка: нет текста или медиа для отправки.")
        await state.clear()
        return

    # 3) Отправляем в чат
    try:
        if media_file_id:
            await call.bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=text)
        else:
            await call.bot.send_message(chat_id=chat_id, text=text)
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
        except Exception as e:
            logger.error(f"Error saving post to database: {e}")
            # Продолжаем выполнение, так как сообщение уже отправлено

    # 5) Успех и возврат в главное меню
    await call.message.edit_text("✅ Пост опубликован!")
    
    # Сохраняем group_id и group_title для следующих операций
    await state.set_data({"group_id": group_pk, "group_title": group.title})
    
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
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
    
    snippet = data.get("text", "")
    if len(snippet) > 50:
        snippet = snippet[:50] + "…"
    
    media_file_id = data.get("media_file_id")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="manual_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="manual_cancel")],
        ]
    )
    
    # Если есть фото, показываем превью с фото
    if media_file_id:
        await message.answer_photo(
            photo=media_file_id,
            caption=f"📝 Предпросмотр запланированного поста:\n\n{snippet}{'...' if len(snippet) > 50 else ''}\n\n🕒 {dt:%d.%m.%Y %H:%M}",
        )
        
        await message.answer(
            "Подтвердить запланированную публикацию?",
            reply_markup=kb
        )
    else:
        # Если фото нет, показываем только текст
        await message.answer(
            f"Вы запланировали:\n\n{snippet}\n\n🕒 {dt:%d.%m.%Y %H:%M}\n\nПодтвердить?",
            reply_markup=kb,
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
    await state.set_data({"group_id": group_pk, "group_title": group.title})
    
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
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
    await state.set_data({"group_id": group_id, "group_title": group_title})
    
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
    await call.answer()
