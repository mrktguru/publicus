# Сначала переименуем старый файл как резервную копию 
mv handlers/group_select.py handlers/group_select.py.bak

# Создадим новый файл с правильной кодировкой
cat > handlers/group_select.py << 'EOF'
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.db import AsyncSessionLocal
from database.models import Group
from keyboards.main import main_menu_kb
import logging

print("🔎 handlers.group_select imported")

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "🔙 Сменить группу")
async def change_group(message: Message):
    # Перенаправляем на выбор группы
    await choose_group(message)

# Выделяем в отдельную функцию, доступную для вызова из других обработчиков
async def choose_group(message: Message):
    # Создадим базовую клавиатуру с настройками
    buttons = [[InlineKeyboardButton(text="⚙️ Настройки групп", callback_data="open_group_settings")]]
    ikb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        # получить все группы, которые добавил этот пользователя
        async with AsyncSessionLocal() as session:
            try:
                # Сначала проверим существование таблицы
                try:
                    # Безопасный запрос - получаем все группы без фильтра
                    query = select(Group)
                    result = await session.execute(query)
                    groups = result.scalars().all()
                    
                    # Если есть группы и поле added_by существует, 
                    # попробуем отфильтровать только для текущего пользователя
                    if groups:
                        try:
                            user_id = message.from_user.id
                            filtered_groups = [g for g in groups if hasattr(g, 'added_by') and g.added_by == user_id]
                            if filtered_groups:
                                groups = filtered_groups
                        except Exception as filter_err:
                            logger.error(f"Error filtering groups: {filter_err}")
                except Exception as e:
                    logger.error(f"Error getting groups: {e}")
                    groups = []
                    
                # собрать inline‑кнопки: сначала группы, затем всегда настройка
                if groups:
                    buttons = [
                        [InlineKeyboardButton(text=g.title, callback_data=f"sel_{g.id}")]
                        for g in groups
                    ]
                    # добавляем кнопку настроек
                    buttons.append([InlineKeyboardButton(text="⚙️ Настройки групп", callback_data="open_group_settings")])
                    ikb = InlineKeyboardMarkup(inline_keyboard=buttons)
                
                if not groups:
                    # нет групп — сообщение + одна кнопка настройки
                    await message.answer(
                        "У вас пока нет групп. Нажмите кнопку ниже, чтобы добавить первую.",
                        reply_markup=ikb
                    )
                    return
    
                # есть группы — просим выбрать
                await message.answer(
                    "Выберите группу, с которой будем работать:",
                    reply_markup=ikb
                )
            except Exception as e:
                logger.error(f"Exception in choose_group: {e}")
                # В случае любой ошибки показываем только кнопку настройки
                await message.answer(
                    "Произошла ошибка при получении списка групп. Нажмите на кнопку ниже, чтобы добавить группу.",
                    reply_markup=ikb
                )
    except Exception as e:
        logger.error(f"Fatal error in choose_group: {e}")
        await message.answer(
            "Произошла ошибка. Пожалуйста, попробуйте снова позже или обратитесь к администратору бота."
        )

@router.callback_query(F.data.startswith("sel_"))
async def select_group(call: CallbackQuery, state: FSMContext):
    try:
        group_id = int(call.data.split("_")[1])
        # запомнить выбор
        await state.set_data({"group_id": group_id})
        # убрать inline‑меню выбора
        await call.message.delete()
        # показать основное reply‑меню
        await call.message.answer(
            "✅ Группа выбрана! Выберите действие:",
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Error in select_group: {e}")
        await call.message.answer("Произошла ошибка при выборе группы. Попробуйте снова.")

@router.callback_query(F.data == "open_group_settings")
async def open_settings(call: CallbackQuery):
    try:
        # удаляем текущее сообщение
        await call.message.delete()
        # отправляем инструкцию по добавлению новой группы
        await call.bot.send_message(
            call.from_user.id,
            "Перешлите боту любое сообщение из группы/канала, чтобы добавить её."
        )
    except Exception as e:
        logger.error(f"Error in open_settings: {e}")
        await call.bot.send_message(
            call.from_user.id,
            "Произошла ошибка. Попробуйте снова или обратитесь к администратору бота."
        )
EOF

# Убедимся, что файл имеет правильные права
chmod 644 handlers/group_select.py

# Проверим содержимое файла
cat handlers/group_select.py | head -5
