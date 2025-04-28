from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from datetime import datetime
from zoneinfo import ZoneInfo                                # ← уже был

from database.db import AsyncSessionLocal
from database.models import Post, Group
from states.post_states import ManualPostStates
from keyboards.main import main_menu_kb

router = Router()

# ── запуск сценария ────────────────────────────────────────────
@router.message(lambda m: m.text and m.text.startswith("📅 Запланировать пост"))
async def start_manual(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("group_id"):
        return await message.answer("❌ Сначала выберите группу через /start")
    await state.set_state(ManualPostStates.waiting_for_text)
    await message.answer("📄 Пришлите текст или фото поста (с подписью):")

# ── ввод текста/фото ───────────────────────────────────────────
@router.message(ManualPostStates.waiting_for_text)
async def input_text_or_photo(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption or ""
        await state.update_data(text=caption, media_file_id=file_id)
    else:
        await state.update_data(text=message.text or "", media_file_id=None)

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
    text = data.get("text", "")
    media_file_id = data.get("media_file_id")
    group_pk = data.get("group_id")

    # 1) Получаем chat_id
    async with SessionLocal() as session:
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
    if media_file_id:
        await call.bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=text)
    else:
        await call.bot.send_message(chat_id=chat_id, text=text)

    # 4) Сохраняем запись в БД
    now_msk = datetime.now(ZoneInfo("Europe/Moscow"))
    async with SessionLocal() as session:
        post = Post(
            chat_id=chat_id,
            text=text,
            media_file_id=media_file_id,
            publish_at=now_msk,            # aware-дата
            created_by=call.from_user.id,
            status="sent",
            published=True,
            published_at=now_msk,
        )
        session.add(post)
        await session.commit()

    # 5) Успех и возврат в главное меню
    await call.message.edit_text("✅ Пост опубликован!")
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
    await state.clear()

# ── запрос времени для планирования ───────────────────────────
@router.callback_query(F.data == "manual_schedule", ManualPostStates.waiting_for_choice)
async def schedule_choice(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "📅 Введите дату и время публикации в формате ДД.MM.ГГГГ ЧЧ:ММ"
    )
    await state.set_state(ManualPostStates.waiting_for_datetime)

# ── ввод даты/времени ──────────────────────────────────────────
@router.message(ManualPostStates.waiting_for_datetime)
async def input_datetime(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Moscow"))     # ← главное исправление
    except ValueError:
        return await message.answer("⛔️ Неверный формат. Пожалуйста: ДД.MM.ГГГГ ЧЧ:ММ")

    await state.update_data(publish_at=dt)
    data = await state.get_data()
    snippet = data["text"] if len(data["text"]) <= 50 else data["text"][:50] + "…"

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

    async with SessionLocal() as session:
        group = await session.get(Group, group_pk)
        chat_id = group.chat_id if group else None
        post = Post(
            chat_id=chat_id,
            text=data.get("text", ""),
            media_file_id=media_file_id,
            publish_at=data.get("publish_at"),      # уже aware-дата из state
            created_by=call.from_user.id,
            status="approved",
        )
        session.add(post)
        await session.commit()

    await call.message.edit_text("✅ Пост запланирован!")
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
    await state.clear()

# ── отмена ─────────────────────────────────────────────────────
@router.callback_query(F.data == "manual_cancel", ManualPostStates.waiting_for_confirm)
async def cancel_manual(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ Планирование отменено.")
    await call.message.answer("Выберите действие:", reply_markup=main_menu_kb())
    await state.clear()
