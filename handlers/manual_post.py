from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
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
@router.message(lambda m: m.text and m.text.startswith("📅 Запланировать пост"))
async def start_manual(message: Message, state: FSMContext):
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
    
    # Переходим к вводу текста поста
    await state.set_state(ManualPostStates.waiting_for_text)
    await message.answer("📄 Пришлите текст или фото поста (с подписью):")

# ── ввод текста/фото ───────────────────────────────────────────
@router.message(ManualPostStates.waiting_for_text)
async def input_text_or_photo(message: Message, state: FSMContext):
    # Сохраняем данные, которые были до этого
    data = await state.get_data()
    group_id = data.get("group_id")
    group_title = data.get("group_title", "")
    
    if message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption or ""
        await state.update_data(text=caption, media_file_id=file_id, group_id=group_id, group_title=group_title)
    else:
        await state.update_data(text=message.text or "", media_file_id=None, group_id=group_id, group_title=group_title)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Опубликовать сразу", callback_data="manual_publish_now"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Запланировать публикацию", callback_data="manual_schedule"
                )
            ],
        ]
    )
    await message.answer("Выберите действие для этого поста:", reply_markup=kb)
    await state.set_state(ManualPostStates.waiting_for_choice)

# ── публикация «сейчас» ────────────────────────────────────────
@router.callback_query(F.data == "manual_publish_now", ManualPostStates.waiting_for_choice)
async def publish_now(call: CallbackQuery, state: FSMContext):
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

# ── запрос времени для планирования ───────────────────────────
@router.callback_query(F.data == "manual_schedule", ManualPostStates.waiting_for_choice)
async def schedule_choice(call: CallbackQuery, state: FSMContext):
    # Сохраним данные состояния перед переходом
    data = await state.get_data()
    
    await call.message.edit_text(
        "📅 Введите дату и время публикации в формате ДД.MM.ГГГГ ЧЧ:ММ"
    )
    await state.set_state(ManualPostStates.waiting_for_datetime)

# ── ввод даты/времени ──────────────────────────────────────────
@router.message(ManualPostStates.waiting_for_datetime)
async def input_datetime(message: Message, state: FSMContext):
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

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="manual_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="manual_cancel")],
        ]
    )
    await message.answer(
        f"Вы запланировали:\n\n{snippet}\n\n🕒 {dt:%d.%m.%Y %H:%M}\n\nПодтвердить?",
        reply_markup=kb,
    )
    await state.set_state(ManualPostStates.waiting_for_confirm)

# ── подтверждение планирования ─────────────────────────────────
@router.callback_query(F.data == "manual_confirm", ManualPostStates.waiting_for_confirm)
async def confirm_manual(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group_pk = data.get("group_id")
    media_file_id = data.get("media_file_id")

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
            text=data.get("text", ""),
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

# ── отмена ─────────────────────────────────────────────────────
@router.callback_query(F.data == "manual_cancel", ManualPostStates.waiting_for_confirm)
async def cancel_manual(call: CallbackQuery, state: FSMContext):
    # Получаем текущие данные состояния
    data = await state.get_data()
    group_id = data.get("group_id")
    group_title = data.get("group_title")
    
    await call.message.edit_text("❌ Планирование отменено.")
    
    # Сохраняем group_id и group_title для следующих операций
    await state.set_data({"group_id": group_id, "group_title": group_title})
    
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
