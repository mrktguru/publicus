from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import AsyncSessionLocal
from database.models import Post   # вместо GeneratedPost
from sqlalchemy import select
from aiogram.fsm.context import FSMContext
from datetime import datetime
from zoneinfo import ZoneInfo          # ← добавили

router = Router()

# ── показать список ожидающих автопостов ───────────────────────

@router.message(lambda m: m.text and m.text.startswith("🕓 Ожидают публикации"))
async def show_pending(message: Message, state: FSMContext):
    async with SessionLocal() as session:
        posts = (
            await session.execute(
                select(GeneratedPost)
                .join(GeneratedSeries)
                .where(
                    GeneratedSeries.chat_id == message.chat.id,
                    GeneratedPost.publish_at > datetime.now(ZoneInfo("Europe/Moscow")),  # ← заменили
                    GeneratedPost.status.in_(["pending", "approved"]),
                )
                .order_by(GeneratedPost.publish_at)
            )
        ).scalars().all()

        if not posts:
            await message.answer("Сейчас нет постов на премодерации.")
            return

        for p in posts:
            text = (
                f"🕓 <strong>{p.publish_at:%d.%m %H:%M}</strong>\n"
                f"Статус: {'⏳ Не проверен' if p.status == 'pending' else '✅ Одобрен'}\n\n"
                f"{p.text[:100]}…"
            )
            kb = (
                InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod_appr_{p.id}")],
                        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod_rej_{p.id}")],
                    ]
                )
                if p.status == "pending"
                else None
            )

            await message.answer(text, reply_markup=kb)

# ── обработка колбэков модерации ────────────────────────────────
@router.callback_query(F.data.startswith("mod_"))
async def moderate(call: CallbackQuery):
    action, post_id = call.data.split("_")[1:]  # appr / rej, id
    async with SessionLocal() as session:
        post = await session.get(GeneratedPost, int(post_id))
        if not post:
            await call.answer("Пост не найден.")
            return

        if action == "appr":
            post.status = "approved"
            txt = "✅ Пост одобрен"
        else:
            post.status = "rejected"
            txt = "❌ Пост отклонён"

        await session.commit()
        await call.message.edit_text(f"{txt} (ID {post.id})")
        await call.answer()
