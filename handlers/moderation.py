from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import AsyncSessionLocal
from database.models import Post   # вместо GeneratedPost
from sqlalchemy import select
from aiogram.fsm.context import FSMContext


router = Router()

@router.callback_query(F.data.startswith("moderate_"))
async def moderate_post(call: CallbackQuery):
    _, action, post_id = call.data.split("_")
    async with SessionLocal() as session:
        post = await session.get(GeneratedPost, int(post_id))
        if not post:
            await call.answer("Пост не найден.")
            return
        if action == "approve":
            post.status = "approved"
            post.moderated_by = call.from_user.id
        elif action == "reject":
            post.status = "rejected"
            post.moderated_by = call.from_user.id
        await session.commit()
    await call.message.edit_text(f"Пост #{post_id} — {'одобрен' if action == 'approve' else 'отклонён'} ✅")