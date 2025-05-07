# handlers/start.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import User, Group
from config import DEFAULT_ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command('start'))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, есть ли пользователь уже в базе
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            existing_user = user_result.scalar_one_or_none()
            
            if existing_user:
                # Проверяем, есть ли у пользователя каналы
                channels_q = select(Group).filter(Group.added_by == user_id)
                channels_result = await session.execute(channels_q)
                channels = channels_result.scalars().all()
                
                if channels:
                    # Если есть каналы, показываем кнопку для их выбора
                    await message.answer(
                        f"📝 <b>Выберите канал или группу для работы</b>\n\n"
                        f"Выберите одну из подключенных групп/каналов или добавьте новую.",
                        parse_mode="HTML",
                        reply_markup=await create_channels_keyboard(user_id)
                    )
                else:
                    # Если каналов нет, предлагаем добавить
                    await message.answer(
                        f"📌 <b>Добавьте первый канал или группу</b>\n\n"
                        f"Чтобы начать работу с ботом, необходимо добавить канал "
                        f"или группу, где бот будет публиковать контент.\n\n"
                        f"⚠️ Для работы бот должен быть администратором с правами "
                        f"на публикацию сообщений.",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="+ Добавить канал", callback_data="add_channel")]
                        ])
                    )
                
                # Обновляем данные пользователя, если они изменились
                if existing_user.username != message.from_user.username or existing_user.full_name != message.from_user.full_name:
                    existing_user.username = message.from_user.username
                    existing_user.full_name = message.from_user.full_name
                    await session.commit()
                    
            else:
                # Новый пользователь - регистрируем
                is_admin = str(user_id) == DEFAULT_ADMIN_ID
                
                new_user = User(
                    user_id=user_id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    role="admin" if is_admin else "account_owner",
                    is_active=True
                )
                
                session.add(new_user)
                await session.commit()
                
                # Отправляем приветственное сообщение
                await message.answer(
                    f"🌟 <b>Добро пожаловать в Publicus!</b>\n\n"
                    f"Я — бот для создания и публикации контента в Telegram-каналах и группах.\n\n"
                    f"✏️ Возможности:\n"
                    f"• Создание постов вручную и с помощью ИИ\n"
                    f"• Запланированная публикация контента\n"
                    f"• Интеграция с Google Таблицами\n"
                    f"• Управление несколькими каналами\n\n"
                    f"🚀 Чтобы начать работу, нажмите кнопку \"Начать\".",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Начать", callback_data="start_onboarding")]
                    ])
                )
                
                logger.info(f"New user registered: {user_id}, {message.from_user.username}")
                
    except Exception as e:
        logger.error(f"Error in /start command: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке команды. Пожалуйста, попробуйте позже."
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
            display_text = f"{'канал' if channel.type == 'channel' else 'группа'} {channel.display_name or channel.title}"
            keyboard.append([InlineKeyboardButton(text=display_text, callback_data=f"select_channel_{channel.id}")])
        
        # Добавляем кнопку для добавления нового канала
        keyboard.append([InlineKeyboardButton(text="+ Добавить канал", callback_data="add_channel")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
