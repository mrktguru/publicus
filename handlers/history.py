from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

from database.db import AsyncSessionLocal
from database.models import Post, Group
from keyboards.main import main_menu_kb

router = Router()

@router.message(F.text == "📜 История")
async def show_history(message: Message, state: FSMContext):
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
# Обновите файл handlers/history.py

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database.db import AsyncSessionLocal
from database.models import Post, Group

router = Router()
logger = logging.getLogger(__name__)

@router.message(lambda m: m.text == "📜 История" or m.text == "История публикаций")
async def history_command(message: Message, state: FSMContext):
    """Обработчик команды истории публикаций через текстовую кнопку"""
    user_data = await state.get_data()
    current_channel = user_data.get("current_channel_title", "текущем канале")
    
    # Здесь код для отображения истории публикаций
    await show_history(message, state, is_callback=False)

@router.callback_query(F.data == "post_history")
async def history_callback(call: CallbackQuery, state: FSMContext):
    """Обработчик инлайн-кнопки 'История публикаций'"""
    logger.info(f"History callback received: {call.data}")
    
    # Здесь код для отображения истории публикаций через callback
    await show_history(call, state, is_callback=True)


async def show_history(source, state: FSMContext, is_callback=False):
    """Общая функция для отображения истории публикаций"""
    try:
        user_data = await state.get_data()
        current_channel = user_data.get("current_channel_title", "текущий канал")
        
        # Проверяем выбран ли канал
        if not user_data.get("group_id") or not user_data.get("chat_id"):
            if is_callback:
                await source.answer("⚠️ Сначала выберите канал для работы", show_alert=True)
                return
            else:
                await source.answer("⚠️ Сначала выберите канал для работы через кнопку 'Сменить группу'")
                return
        
        chat_id = user_data["chat_id"]
        
        async with AsyncSessionLocal() as session:
            # Получаем опубликованные посты за последние 30 дней
            now = datetime.now(ZoneInfo("Europe/Moscow"))
            month_ago = now - timedelta(days=30)
            
            query = (
                select(Post)
                .filter(
                    Post.chat_id == chat_id,
                    Post.published == True,
                    Post.publish_at >= month_ago
                )
                .order_by(Post.publish_at.desc())
            )
            
            result = await session.execute(query)
            published_posts = result.scalars().all()
            
            if not published_posts:
                # Если нет опубликованных постов
                history_text = f"📋 <b>История публикаций канала \"{current_channel}\"</b>\n\n" \
                              f"За последние 30 дней не было опубликовано ни одного поста."
            else:
                # Если есть опубликованные посты
                posts_text = "\n\n".join([
                    f"📤 <b>{post.publish_at.strftime('%d.%m.%Y %H:%M')}</b>\n"
                    f"{post.text[:100]}{'...' if len(post.text) > 100 else ''}"
                    for post in published_posts[:10]  # Ограничиваем до 10 постов
                ])
                
                history_text = f"📋 <b>История публикаций канала \"{current_channel}\"</b>\n\n" \
                              f"{posts_text}\n\n" \
                              f"Всего опубликовано: {len(published_posts)} постов за 30 дней."
            
            # Создаем клавиатуру с кнопкой возврата
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
            ])
            
            # Отправляем сообщение с историей
            if is_callback:
                try:
                    await source.message.edit_text(history_text, parse_mode="HTML", reply_markup=keyboard)
                    await source.answer()
                except Exception as e:
                    logger.error(f"Error editing message: {e}")
                    await source.message.answer(history_text, parse_mode="HTML", reply_markup=keyboard)
                    await source.answer()
            else:
                await source.answer(history_text, parse_mode="HTML", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error showing history: {e}")
        error_message = "⚠️ Произошла ошибка при загрузке истории публикаций."
        
        if is_callback:
            await source.answer(error_message, show_alert=True)
        else:
            await source.answer(error_message)
