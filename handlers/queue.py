from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from database.db import AsyncSessionLocal
from database.models import Post
from sqlalchemy import select
from datetime import datetime
from zoneinfo import ZoneInfo

router = Router()

PAGE_SIZE = 10

def build_page(posts: list[Post], page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Формирует текст и клавиатуру для страницы `page` (0-based)."""
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    slice_ = posts[start:end]

    text_lines = [
        f"🗕️ Запланированные посты (стр. {page + 1}/{(len(posts) - 1) // PAGE_SIZE + 1}):\n"
    ]
    for p in slice_:
        text_lines.append(f"• {p.publish_at:%d.%m %H:%M} — {p.text[:50]}…")
    text = "\n".join(text_lines)

    # навигация
    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="⏪ Назад", callback_data=f"queue_page_{page-1}")
        )
    if end < len(posts):
        buttons.append(
            InlineKeyboardButton(text="Вперёд ⏩", callback_data=f"queue_page_{page+1}")
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
    return text, kb

# —— команда /queue ——
@router.message(Command("queue"))
async def handle_queue_command(message: Message):
    await show_queue(message)

@router.message(lambda m: m.text and m.text.lower().startswith("очередь"))
async def handle_queue_text(message: Message):
    await show_queue(message)

async def show_queue(message: Message):
    async with AsyncSessionLocal() as session:
        posts = (
            await session.execute(
                select(Post).where(
                    Post.status == "approved",
                    Post.publish_at > datetime.now(ZoneInfo("Europe/Moscow")),
                ).order_by(Post.publish_at)
            )
        ).scalars().all()

    if not posts:
        return await message.answer("Очередь пуста 🤷‍♂️")

    text, kb = build_page(posts, page=0)
    await message.answer(text, reply_markup=kb)

# —— обработка пагинации ——
@router.callback_query(F.data.startswith("queue_page_"))
async def paginate_queue(call: CallbackQuery):
    page = int(call.data.split("_")[-1])

    async with AsyncSessionLocal() as session:
        posts = (
            await session.execute(
                select(Post).where(
                    Post.status == "approved",
                    Post.publish_at > datetime.now(ZoneInfo("Europe/Moscow")),
                ).order_by(Post.publish_at)
            )
        ).scalars().all()

    if not posts:
        await call.message.edit_text("Очередь пуста 🤷‍♂️")
        return await call.answer()

    text, kb = build_page(posts, page)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
