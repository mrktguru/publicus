from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Chat
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from database.db import AsyncSessionLocal
from database.models import Group
from keyboards.main import main_menu_kb
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "open_group_settings")
async def open_group_settings(call: CallbackQuery):
    """Обрабатывает открытие настроек групп."""
    try:
        # Получаем список групп пользователя
        async with AsyncSessionLocal() as session:
            query = select(Group).where(Group.added_by == call.from_user.id)
            result = await session.execute(query)
            groups = result.scalars().all()
        
        if not groups:
            await call.message.edit_text(
                "У вас пока нет добавленных групп. "
                "Перешлите мне любое сообщение из группы/канала, чтобы добавить его."
            )
            return
        
        # Формируем список групп
        groups_text = "Ваши группы:\n\n"
        for i, group in enumerate(groups, 1):
            groups_text += f"{i}. {group.title} [ID: {group.chat_id}]\n"
        
        groups_text += "\n• Перешлите сообщение из новой группы, чтобы добавить её"
        groups_text += "\n• Отправьте ID группы, чтобы удалить её (например, 'удалить -1001234567890')"
        
        await call.message.edit_text(groups_text)
    
    except Exception as e:
        logger.error(f"Error in open_group_settings: {e}")
        await call.message.edit_text(
            "Произошла ошибка при получении списка групп. Попробуйте еще раз или обратитесь к администратору."
        )


@router.message(F.forward_from_chat.as_("forwarded_chat"))
async def add_group_by_forward(message: Message, forwarded_chat: Chat, state: FSMContext):
    """Обрабатывает пересланное сообщение для добавления группы."""
    try:
        # Добавляем группу в БД
        async with AsyncSessionLocal() as session:
            # Проверяем, есть ли уже такая группа
            query = select(Group).where(Group.chat_id == forwarded_chat.id)
            result = await session.execute(query)
            existing_group = result.scalars().first()
            
            if existing_group:
                group_id = existing_group.id
                await message.answer(f"✅ Группа «{forwarded_chat.title}» уже добавлена!")
            else:
                # Добавляем новую группу
                new_group = Group(
                    chat_id=forwarded_chat.id,
                    title=forwarded_chat.title,
                    added_by=message.from_user.id
                )
                session.add(new_group)
                await session.flush()  # Чтобы получить ID
                group_id = new_group.id
                await session.commit()
                await message.answer(f"✅ Группа «{forwarded_chat.title}» добавлена!")
            
            # Важно: сразу же устанавливаем эту группу как активную
            await state.set_data({"group_id": group_id, "chat_id": forwarded_chat.id})
            
            # Показываем основное меню без необходимости дополнительно нажимать /start
            await message.answer(
                f"👍 Группа «{forwarded_chat.title}» выбрана для работы! Выберите действие:",
                reply_markup=main_menu_kb()
            )
    
    except Exception as e:
        logger.error(f"Error in add_group_by_forward: {e}")
        await message.answer(
            "❌ Произошла ошибка при добавлении группы. "
            "Убедитесь, что вы переслали сообщение из группы или канала, "
            "и что бот является администратором этой группы/канала."
        )


@router.message(lambda message: message.text and message.text.lower().startswith("удалить "))
async def delete_group(message: Message):
    """Обрабатывает запрос на удаление группы."""
    try:
        # Извлекаем ID группы из сообщения
        try:
            chat_id = int(message.text.split("удалить ")[1].strip())
        except (ValueError, IndexError):
            await message.answer(
                "❌ Неверный формат. Используйте: удалить <ID группы>\n"
                "Например: удалить -1001234567890"
            )
            return
        
        # Удаляем группу из БД
        async with AsyncSessionLocal() as session:
            # Проверяем, есть ли такая группа у пользователя
            query = select(Group).where(Group.chat_id == chat_id, Group.added_by == message.from_user.id)
            result = await session.execute(query)
            group = result.scalars().first()
            
            if not group:
                await message.answer(f"❌ Группа с ID {chat_id} не найдена или не принадлежит вам.")
                return
            
            # Удаляем группу
            await session.execute(delete(Group).where(Group.id == group.id))
            await session.commit()
            
            await message.answer(f"✅ Группа «{group.title}» удалена!")
    
    except Exception as e:
        logger.error(f"Error in delete_group: {e}")
        await message.answer(
            "❌ Произошла ошибка при удалении группы. Попробуйте еще раз или обратитесь к администратору."
        )


@router.message(lambda message: message.text and message.text == "⚙️ Настройки групп")
async def group_settings_button(message: Message):
    """Обрабатывает нажатие на кнопку настроек групп."""
    try:
        # Получаем список групп пользователя
        async with AsyncSessionLocal() as session:
            query = select(Group).where(Group.added_by == message.from_user.id)
            result = await session.execute(query)
            groups = result.scalars().all()
        
        if not groups:
            await message.answer(
                "У вас пока нет добавленных групп. "
                "Перешлите мне любое сообщение из группы/канала, чтобы добавить его."
            )
            return
        
        # Формируем список групп
        groups_text = "Ваши группы:\n\n"
        for i, group in enumerate(groups, 1):
            groups_text += f"{i}. {group.title} [ID: {group.chat_id}]\n"
        
        groups_text += "\n• Перешлите сообщение из новой группы, чтобы добавить её"
        groups_text += "\n• Отправьте ID группы, чтобы удалить её (например, 'удалить -1001234567890')"
        
        await message.answer(groups_text)
    
    except Exception as e:
        logger.error(f"Error in group_settings_button: {e}")
        await message.answer(
            "Произошла ошибка при получении списка групп. Попробуйте еще раз или обратитесь к администратору."
        )
