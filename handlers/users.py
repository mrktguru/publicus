# handlers/users.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update

from database.db import AsyncSessionLocal
from database.models import User
from config import DEFAULT_ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)

class UserStates(StatesGroup):
    """Состояния для процесса управления пользователями"""
    waiting_for_email = State()

@router.message(Command('start'))
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start
    
    Приветствует пользователя и регистрирует его в системе, если это новый пользователь.
    Если пользователь уже зарегистрирован, отображает приветственное сообщение.
    """
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, есть ли пользователь уже в базе
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            existing_user = user_result.scalar_one_or_none()
            
            if existing_user:
                # Пользователь уже зарегистрирован
                await message.answer(
                    f"🌟 <b>С возвращением в Publicus!</b>\n\n"
                    f"Я — бот для создания и публикации контента в Telegram-каналах и группах.\n\n"
                    f"Давайте вместе создавать и публиковать контент! Чтобы начать, добавьте канал или группу.",
                    parse_mode="HTML"
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

@router.callback_query(lambda c: c.data == "start_onboarding")
async def start_onboarding(call: CallbackQuery, state: FSMContext):
    """Начало процесса онбординга нового пользователя"""
    await call.message.edit_text(
        "📧 <b>Для завершения регистрации</b>\n\n"
        "Пожалуйста, введите ваш email для важных уведомлений о работе бота.\n"
        "Мы будем использовать его только для отправки важных системных сообщений.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_email")]
        ])
    )
    
    await state.set_state(UserStates.waiting_for_email)

@router.message(UserStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    """Обработка ввода email пользователя"""
    email = message.text.strip().lower()
    user_id = message.from_user.id
    
    # Простая проверка формата email
    if '@' not in email or '.' not in email:
        await message.answer(
            "⚠️ Введенный email некорректен. Пожалуйста, проверьте и попробуйте снова.\n"
            "Или нажмите кнопку \"Пропустить\" для продолжения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_email")]
            ])
        )
        return
    
    # Сохраняем email
    try:
        async with AsyncSessionLocal() as session:
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one()
            
            user.email = email
            await session.commit()
            
            # Продолжаем процесс
            await show_add_channel_prompt(message)
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error saving user email: {e}")
        await message.answer("⚠️ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")

@router.callback_query(lambda c: c.data == "skip_email")
async def skip_email(call: CallbackQuery, state: FSMContext):
    """Пропуск ввода email при регистрации"""
    await call.message.edit_text("✅ Email пропущен. Вы всегда можете добавить его позже в настройках.")
    await show_add_channel_prompt(call.message)
    await state.clear()

async def show_add_channel_prompt(message: Message):
    """Показ предложения добавить канал/группу"""
    await message.answer(
        "📌 <b>Добавьте первый канал или группу</b>\n\n"
        "Чтобы начать работу с ботом, необходимо добавить канал "
        "или группу, где бот будет публиковать контент.\n\n"
        "⚠️ Для работы бот должен быть администратором с правами "
        "на публикацию сообщений.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="+ Добавить канал", callback_data="add_channel")]
        ])
    )

@router.message(Command(commands=['admin', 'users']))
async def admin_users_list(message: Message):
    """
    Администраторская команда для просмотра списка пользователей.
    Доступна только пользователям с ролью 'admin'.
    """
    user_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, является ли пользователь администратором
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or user.role != 'admin':
                await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
                return
            
            # Получаем список всех пользователей
            all_users_q = select(User).order_by(User.id)
            all_users_result = await session.execute(all_users_q)
            users = all_users_result.scalars().all()
            
            if not users:
                await message.answer("📊 В системе пока нет зарегистрированных пользователей.")
                return
            
            # Формируем список пользователей
            users_text = "\n\n".join([
                f"👤 <b>ID:</b> {user.user_id}\n"
                f"📝 <b>Имя:</b> {user.full_name or 'Не указано'}\n"
                f"👤 <b>Username:</b> {('@' + user.username) if user.username else 'Не указано'}\n"
                f"📧 <b>Email:</b> {user.email or 'Не указано'}\n"
                f"🔑 <b>Роль:</b> {'Администратор' if user.role == 'admin' else 'Обычный пользователь'}\n"
                f"🔄 <b>Статус:</b> {'Активен' if user.is_active else 'Заблокирован'}"
                for user in users
            ])
            
            await message.answer(
                f"📊 <b>Список пользователей системы ({len(users)})</b>\n\n"
                f"{users_text}\n\n"
                f"Используйте следующие команды для управления:\n"
                f"/makeadmin [user_id] - назначить администратором\n"
                f"/blockuser [user_id] - заблокировать пользователя\n"
                f"/unblockuser [user_id] - разблокировать пользователя",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Error getting users list: {e}")
        await message.answer("⚠️ Произошла ошибка при получении списка пользователей.")

@router.message(Command(commands=['makeadmin']))
async def make_admin(message: Message):
    """Назначение пользователя администратором"""
    user_id = message.from_user.id
    
    # Получаем ID пользователя для повышения из аргументов команды
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Неверный формат команды. Используйте: /makeadmin [user_id]")
        return
    
    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID пользователя должен быть числом.")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, является ли пользователь администратором
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or user.role != 'admin':
                await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
                return
            
            # Находим целевого пользователя
            target_user_q = select(User).filter(User.user_id == target_user_id)
            target_user_result = await session.execute(target_user_q)
            target_user = target_user_result.scalar_one_or_none()
            
            if not target_user:
                await message.answer(f"⚠️ Пользователь с ID {target_user_id} не найден.")
                return
            
            # Назначаем пользователя администратором
            target_user.role = 'admin'
            await session.commit()
            
            await message.answer(
                f"✅ Пользователь {target_user.full_name} (ID: {target_user_id}) назначен администратором."
            )
            
    except Exception as e:
        logger.error(f"Error making user admin: {e}")
        await message.answer("⚠️ Произошла ошибка при назначении пользователя администратором.")

@router.message(Command(commands=['blockuser']))
async def block_user(message: Message):
    """Блокировка пользователя"""
    user_id = message.from_user.id
    
    # Получаем ID пользователя для блокировки из аргументов команды
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Неверный формат команды. Используйте: /blockuser [user_id]")
        return
    
    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID пользователя должен быть числом.")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, является ли пользователь администратором
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or user.role != 'admin':
                await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
                return
            
            # Находим целевого пользователя
            target_user_q = select(User).filter(User.user_id == target_user_id)
            target_user_result = await session.execute(target_user_q)
            target_user = target_user_result.scalar_one_or_none()
            
            if not target_user:
                await message.answer(f"⚠️ Пользователь с ID {target_user_id} не найден.")
                return
            
            # Блокируем пользователя
            target_user.is_active = False
            await session.commit()
            
            await message.answer(
                f"✅ Пользователь {target_user.full_name} (ID: {target_user_id}) заблокирован."
            )
            
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        await message.answer("⚠️ Произошла ошибка при блокировке пользователя.")

@router.message(Command(commands=['unblockuser']))
async def unblock_user(message: Message):
    """Разблокировка пользователя"""
    user_id = message.from_user.id
    
    # Получаем ID пользователя для разблокировки из аргументов команды
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Неверный формат команды. Используйте: /unblockuser [user_id]")
        return
    
    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID пользователя должен быть числом.")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем, является ли пользователь администратором
            user_q = select(User).filter(User.user_id == user_id)
            user_result = await session.execute(user_q)
            user = user_result.scalar_one_or_none()
            
            if not user or user.role != 'admin':
                await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
                return
            
            # Находим целевого пользователя
            target_user_q = select(User).filter(User.user_id == target_user_id)
            target_user_result = await session.execute(target_user_q)
            target_user = target_user_result.scalar_one_or_none()
            
            if not target_user:
                await message.answer(f"⚠️ Пользователь с ID {target_user_id} не найден.")
                return
            
            # Разблокируем пользователя
            target_user.is_active = True
            await session.commit()
            
            await message.answer(
                f"✅ Пользователь {target_user.full_name} (ID: {target_user_id}) разблокирован."
            )
            
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        await message.answer("⚠️ Произошла ошибка при разблокировке пользователя.")
