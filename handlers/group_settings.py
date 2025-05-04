from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.db import AsyncSessionLocal
from database.models import Group
from keyboards.main import main_menu_kb
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.forward_from_chat)
async def add_group(message: Message, state: FSMContext):
    """
    Добавляет группу в БД, если пользователь переслал сообщение из чата.
    
    Доступно только после нажатия на кнопку «⚙️ Настройки групп».
    """
    # восстанавливаем данные из FSM
    data = await state.get_data()
    
    # получаем идентификаторы
    chat_id = message.forward_from_chat.id
    chat_title = message.forward_from_chat.title or message.forward_from_chat.username
    user_id = message.from_user.id
    
    if not chat_title:
        await message.answer(
            "❌ Не удалось определить название группы/канала. "
            "Пожалуйста, перешлите сообщение из группы/канала с названием."
        )
        return
    
    # добавляем запись в базу
    try:
        async with AsyncSessionLocal() as session:
            # проверяем, существует ли уже такая группа
            query = select(Group).where(Group.chat_id == chat_id)
            result = await session.execute(query)
            existing_group = result.scalars().first()
            
            if existing_group:
                # Проверяем атрибут added_by только если он существует
                try:
                    if hasattr(existing_group, 'added_by') and existing_group.added_by != user_id:
                        # Если группа добавлена другим пользователем
                        await message.answer(
                            "❌ Эта группа уже добавлена другим пользователем."
                        )
                        return
                    else:
                        # Если группа уже есть у этого пользователя или added_by не существует
                        await message.answer(
                            f"ℹ️ Группа «{chat_title}» уже добавлена."
                        )
                        return
                except Exception as attr_err:
                    logger.error(f"Error checking added_by: {attr_err}")
                    await message.answer(
                        f"ℹ️ Группа «{chat_title}» уже добавлена."
                    )
                    return
                
            # добавляем новую группу
            try:
                # Проверяем, какие атрибуты доступны в модели Group
                group_attributes = {}
                group_attributes['chat_id'] = chat_id
                group_attributes['title'] = chat_title
                
                # Попробуем добавить added_by, только если это поле есть в модели
                try:
                    # Проверка структуры таблицы через первый экземпляр
                    sample_group = Group()
                    if hasattr(sample_group, 'added_by'):
                        group_attributes['added_by'] = user_id
                except Exception:
                    pass
                
                group = Group(**group_attributes)
                session.add(group)
                await session.commit()
                
                await message.answer(
                    f"✅ Группа «{chat_title}» добавлена!\n\n"
                    f"❗ Убедитесь, что бот добавлен в группу/канал и имеет "
                    f"права администратора на публикацию сообщений.\n\n"
                    f"Выберите действие:",
                    reply_markup=main_menu_kb()
                )
            except Exception as group_err:
                logger.error(f"Error creating group: {group_err}")
                await message.answer(f"❌ Ошибка при создании группы: {group_err}")
    except Exception as e:
        logger.error(f"Database error: {e}")
        await message.answer(f"❌ Ошибка при добавлении группы: {e}")
