# handlers/queue.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from datetime import datetime

from database.db import AsyncSessionLocal
from database.models import Post, Group
from keyboards.main import main_menu_kb

router = Router()


@router.message(F.text == "📋 Очередь публикаций")
async def show_queue(message: Message, state: FSMContext):
    data = await state.get_data()
    group_id = data.get("group_id")
    if not group_id:
        return await message.answer("❌ Сначала выберите группу через /start")

    async with AsyncSessionLocal() as s:
        group = await s.get(Group, group_id)
        if not group:
            return await message.answer("❌ Группа не найдена.")
        q = (
            select(Post)
            .where(
                and_(
                    Post.chat_id == group.chat_id,
                    Post.status == "approved",
                    Post.published.is_(False),
                )
            )
            .order_by(Post.publish_at)
        )
        posts = (await s.execute(q)).scalars().all()

    if not posts:
        return await message.answer("📦 Очередь пуста.", reply_markup=main_menu_kb())

    lines = [
        f"🕒 {p.publish_at:%d.%m %H:%M} — { (p.text or '')[:40]}…" for p in posts
    ]
    await message.answer(
        "<b>📋 Очередь публикаций:</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
