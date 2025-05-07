# utils/keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.db import AsyncSessionLocal
from database.models import Group

async def create_main_keyboard():
    """Создает основную клавиатуру с меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать пост")],
            [KeyboardButton(text="Контент план"), KeyboardButton(text="История публикаций")],
            [KeyboardButton(text="Таблицы"), KeyboardButton(text="Настройки")],
            [KeyboardButton(text="Сменить группу")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

async def create_channels_keyboard(user_id):
    """Создает клавиатуру со списком каналов/групп пользователя"""
    async with AsyncSessionLocal() as session:
        # Получаем все каналы пользователя
        channels_q = select(Group).filter(Group.added_by == user_id)
        channels_result = await session.execute(channels_q)
        channels = channels_result.scalars().all()
        
        # Создаем inline-клавиатуру
        keyboard = []
        for channel in channels:
            # Безопасно получаем атрибуты, используя getattr с значениями по умолчанию
            channel_type = getattr(channel, 'type', 'channel')
            display_name = getattr(channel, 'display_name', channel.title)
            
            display_text = f"{'канал' if channel_type == 'channel' else 'группа'} {display_name or channel.title}"
            keyboard.append([InlineKeyboardButton(text=display_text, callback_data=f"select_channel_{channel.id}")])
        
        # Добавляем кнопку для добавления нового канала
        keyboard.append([InlineKeyboardButton(text="+ Добавить канал", callback_data="add_channel")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

