from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

from database.db import SessionLocal
from database.models import Post, Group
from keyboards.main import main_menu_kb

router = Router()

@router.message(F.text == "📜 История")
async def show_history(message: Message, state: FSMContext):
    data = await state.get_data()
    group_id = data.get("group_id")
    if not group_id:
        return await message.answer("❌ Сначала выберите группу через /start")

    async with SessionLocal() as s:
        group = await s.get(Group, group_id)
        if not group:
            return await message.answer("❌ Группа не найдена.")
        q = (
            select(Post)
            .where(and_(Post.chat_id == group.chat_id, Post.status == "sent"))
            .order_by(Post.publish_at.desc())
            .limit(30)
        )
        posts = (await s.execute(q)).scalars().all()

    if not posts:
        return await message.answer("История пуста.", reply_markup=main_menu_kb())

    lines = [
        f"✔️ {p.publish_at:%d.%m %H:%M} — { (p.text or '')[:40]}…" for p in posts
    ]
    await message.answer(
        "<b>📜 Последние публикации:</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
