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

# Добавьте этот код в файл handlers/queue.py
@router.callback_query(F.data == "show_schedule")
async def show_schedule_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик инлайн-кнопки 'Контент план'"""
    logger.info(f"Show schedule callback received: {call.data}")
    
    user_id = call.from_user.id
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущий канал")
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем выбран ли канал
            if not user_data.get("group_id") or not user_data.get("chat_id"):
                await call.answer("⚠️ Сначала выберите канал для работы", show_alert=True)
                return
            
            chat_id = user_data["chat_id"]
            
            # Получаем запланированные посты
            now = datetime.now(ZoneInfo("Europe/Moscow"))
            query = (
                select(Post)
                .filter(
                    Post.chat_id == chat_id,
                    Post.status == "approved",
                    Post.published == False,
                    Post.publish_at > now
                )
                .order_by(Post.publish_at)
            )
            
            result = await session.execute(query)
            scheduled_posts = result.scalars().all()
            
            if not scheduled_posts:
                # Если нет запланированных постов
                await call.message.edit_text(
                    f"📅 <b>Контент план канала \"{current_channel}\"</b>\n\n"
                    f"В данный момент нет запланированных публикаций.\n\n"
                    f"Чтобы создать новый пост, используйте кнопку 'Создать пост'.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Создать пост", callback_data="post:create_manual")],
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
                    ])
                )
            else:
                # Если есть запланированные посты
                posts_text = "\n\n".join([
                    f"🕒 <b>{post.publish_at.strftime('%d.%m.%Y %H:%M')}</b>\n"
                    f"{post.text[:100]}{'...' if len(post.text) > 100 else ''}"
                    for post in scheduled_posts[:10]  # Ограничиваем до 10 постов
                ])
                
                await call.message.edit_text(
                    f"📅 <b>Контент план канала \"{current_channel}\"</b>\n\n"
                    f"{posts_text}\n\n"
                    f"Всего запланировано: {len(scheduled_posts)} постов.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Создать пост", callback_data="post:create_manual")],
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
                    ])
                )
                
            await call.answer()
            
    except Exception as e:
        logger.error(f"Error showing schedule: {e}")
        await call.answer("⚠️ Произошла ошибка при загрузке контент-плана", show_alert=True)
