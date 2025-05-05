from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
from datetime import datetime, timezone
import asyncio
import logging
from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import GenerationTemplate, Post, Group
from gpt_client import generate_article

# Константы для выбора опций
CONTENT_TYPES = {
    "news": "Новостной",
    "edu": "Образовательный",
    "fun": "Развлекательный",
    "anl": "Аналитический",
    "mot": "Мотивационный",
    "dis": "Дискуссионный"
}

TONES = {
    "formal": "Официальный/формальный",
    "neutral": "Нейтральный",
    "friendly": "Дружелюбный/разговорный",
    "emotional": "Эмоциональный/восторженный",
    "humor": "Юмористический"
}

STRUCTURE_OPTIONS = {
    "title": "Заголовок",
    "main": "Основной текст",
    "quote": "Выделенная цитата",
    "conclusion": "Заключение/вывод",
    "hashtags": "Хэштеги",
    "emoji": "Эмодзи"
}

LENGTH_OPTIONS = {
    "short": "Короткий (до 300 символов)",
    "medium": "Средний (300-800 символов)",
    "long": "Длинный (800-1500 символов)"
}

router = Router()
logger = logging.getLogger(__name__)

class AutoGenStates(StatesGroup):
    # Состояния для персонализированной настройки
    content_type = State()
    themes = State()
    tone = State()
    structure = State()
    length = State()
    post_count = State()
    preview = State()
    moderation = State()
    confirmation = State()


@router.message(lambda m: m.text and m.text.startswith("🤖 Автогенерация постов"))
async def start_auto_gen(message: Message, state: FSMContext):
    """Начальный обработчик для автогенерации постов"""
    # Получаем текущую выбранную группу
    user_data = await state.get_data()
    group_id = user_data.get("group_id")
    
    if not group_id:
        await message.answer(
            "⚠️ Сначала выберите группу или канал для работы.\n"
            "Используйте кнопку '🔙 Сменить группу' в главном меню."
        )
        return
    
    # Сохраняем group_id в состоянии
    await state.update_data(group_id=group_id)
    
    # Определяем chat_id для выбранной группы
    try:
        async with AsyncSessionLocal() as session:
            group = await session.get(Group, group_id)
            if group:
                await state.update_data(chat_id=group.chat_id)
    except Exception as e:
        logger.error(f"Error fetching group: {e}")
    
    # Создаем клавиатуру с типами контента
    kb = []
    for code, name in CONTENT_TYPES.items():
        kb.append([InlineKeyboardButton(text=name, callback_data=f"ct_{code}")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await message.answer(
        "Шаг 1: Выберите основной тип контента для генерации:",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.content_type)


# Обработчик выбора типа контента
@router.callback_query(AutoGenStates.content_type, F.data.startswith("ct_"))
async def process_content_type(call: CallbackQuery, state: FSMContext):
    content_type_code = call.data.split("_")[1]
    content_type_name = CONTENT_TYPES[content_type_code]
    
    # Сохраняем выбор в состоянии
    await state.update_data(content_type_code=content_type_code, content_type_name=content_type_name)
    
    await call.message.edit_text(
        f"✅ Выбран тип контента: {content_type_name}\n\n"
        f"Шаг 2: Введите ключевые слова или темы, разделенные запятыми:\n\n"
        f"Например: Манчестер Юнайтед, АПЛ, трансферы"
    )
    
    await state.set_state(AutoGenStates.themes)


@router.message(AutoGenStates.themes)
async def process_themes(message: Message, state: FSMContext):
    themes = message.text.strip()
    
    # Сохраняем темы
    await state.update_data(themes=themes)
    
    # Создаем клавиатуру для выбора тона
    kb = []
    for code, name in TONES.items():
        kb.append([InlineKeyboardButton(text=name, callback_data=f"tone_{code}")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await message.answer(
        f"✅ Темы сохранены: {themes}\n\n"
        f"Шаг 3: Выберите тон повествования:",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.tone)


@router.callback_query(AutoGenStates.tone, F.data.startswith("tone_"))
async def process_tone(call: CallbackQuery, state: FSMContext):
    tone_code = call.data.split("_")[1]
    tone_name = TONES[tone_code]
    
    # Сохраняем тон
    await state.update_data(tone_code=tone_code, tone_name=tone_name)
    
    # Создаем клавиатуру для структуры (множественный выбор)
    structure_kb = []
    
    for code, name in STRUCTURE_OPTIONS.items():
        # По умолчанию выбираем основной текст
        is_selected = (code == "main")
        checkbox = "☑️" if is_selected else "⬜"
        structure_kb.append([
            InlineKeyboardButton(
                text=f"{checkbox} {name}", 
                callback_data=f"struct_{code}_{1 if is_selected else 0}"
            )
        ])
    
    # Добавляем кнопку подтверждения
    structure_kb.append([InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="struct_confirm")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=structure_kb)
    
    await call.message.edit_text(
        f"✅ Выбран тон: {tone_name}\n\n"
        f"Шаг 4: Выберите компоненты структуры поста (можно выбрать несколько):",
        reply_markup=markup
    )
    
    # Инициализируем структуру с основным текстом по умолчанию
    await state.update_data(structure={"main": True})
    await state.set_state(AutoGenStates.structure)


@router.callback_query(AutoGenStates.structure, F.data.startswith("struct_"))
async def process_structure_selection(call: CallbackQuery, state: FSMContext):
    data = call.data.split("_")
    
    # Если это подтверждение выбора
    if data[1] == "confirm":
        # Переходим к выбору длины
        kb = []
        for code, name in LENGTH_OPTIONS.items():
            kb.append([InlineKeyboardButton(text=name, callback_data=f"len_{code}")])
        
        markup = InlineKeyboardMarkup(inline_keyboard=kb)
        
        # Получаем текущую структуру
        user_data = await state.get_data()
        structure = user_data.get("structure", {})
        
        # Формируем текстовое представление выбранной структуры
        selected_items = [name for code, name in STRUCTURE_OPTIONS.items() if structure.get(code, False)]
        structure_text = ", ".join(selected_items)
        
        await call.message.edit_text(
            f"✅ Выбрана структура: {structure_text}\n\n"
            f"Шаг 5: Выберите предпочтительную длину поста:",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.length)
        return
    
    # Иначе обрабатываем выбор элемента структуры
    component = data[1]
    is_selected = int(data[2]) == 1
    
    # Инвертируем состояние выбора
    new_state = 0 if is_selected else 1
    
    # Обновляем состояние
    user_data = await state.get_data()
    structure = user_data.get("structure", {})
    structure[component] = not is_selected
    await state.update_data(structure=structure)
    
    # Обновляем клавиатуру
    structure_kb = []
    for code, name in STRUCTURE_OPTIONS.items():
        checkbox = "☑️" if structure.get(code, False) else "⬜"
        structure_kb.append([
            InlineKeyboardButton(
                text=f"{checkbox} {name}", 
                callback_data=f"struct_{code}_{1 if structure.get(code, False) else 0}"
            )
        ])
    
    # Добавляем кнопку подтверждения
    structure_kb.append([InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="struct_confirm")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=structure_kb)
    
    await call.message.edit_reply_markup(reply_markup=markup)


@router.callback_query(AutoGenStates.length, F.data.startswith("len_"))
async def process_length(call: CallbackQuery, state: FSMContext):
    length_code = call.data.split("_")[1]
    length_name = LENGTH_OPTIONS[length_code]
    
    # Сохраняем длину
    await state.update_data(length_code=length_code, length_name=length_name)
    
    await call.message.edit_text(
        f"✅ Выбрана длина: {length_name}\n\n"
        f"Шаг 6: Введите количество постов для генерации (от 1 до 30):"
    )
    
    await state.set_state(AutoGenStates.post_count)


@router.message(AutoGenStates.post_count)
async def process_post_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1:
            count = 1
        elif count > 30:
            count = 30
    except ValueError:
        count = 5  # По умолчанию
    
    # Сохраняем количество
    await state.update_data(post_count=count)
    
    # Генерируем пример поста
    user_data = await state.get_data()
    
    await message.answer("⏳ Генерируем пример поста на основе выбранных параметров...")
    
    # Формируем параметры для генерации примера
    try:
        # Формируем базовый промпт
        content_type = user_data["content_type_name"]
        themes = user_data["themes"]
        tone = user_data["tone_name"]
        structure = user_data["structure"]
        
        structure_text = []
        if structure.get("title", False):
            structure_text.append("заголовок")
        if structure.get("main", False):
            structure_text.append("основной текст")
        if structure.get("quote", False):
            structure_text.append("выделенную цитату")
        if structure.get("conclusion", False):
            structure_text.append("заключение/вывод")
        if structure.get("hashtags", False):
            structure_text.append("хэштеги")
        
        length_text = user_data["length_name"].split(" ")[0].lower()
        
        # Формируем промпт для генерации примера
        prompt = (
            f"Создай {content_type} пост на тему '{themes}' в {tone} тоне. "
            f"Пост должен включать {', '.join(structure_text)}. "
            f"Длина поста: {length_text}. "
        )
        
        # Добавляем эмодзи если нужно
        if structure.get("emoji", False):
            prompt += " Добавь подходящие эмодзи для украшения текста."
        
        # Генерируем пример поста
        example_text = await generate_article(prompt)
        
        # Сохраняем пример поста
        await state.update_data(example_text=example_text)
        
        # Создаем клавиатуру для подтверждения
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Всё верно", callback_data="preview_ok")],
            [InlineKeyboardButton(text="🔄 Сгенерировать другой пример", callback_data="preview_regen")],
            [InlineKeyboardButton(text="⬅️ Вернуться к настройкам", callback_data="preview_back")]
        ])
        
        await message.answer(
            f"📝 Пример поста на основе выбранных параметров:\n\n"
            f"{example_text}\n\n"
            f"Вас устраивает этот формат?",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.preview)
    
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        await message.answer(
            f"❌ Не удалось сгенерировать пример поста.\n"
            f"Пожалуйста, попробуйте еще раз или измените параметры."
        )
        # Возвращаемся к выбору количества постов
        await state.set_state(AutoGenStates.post_count)


@router.callback_query(AutoGenStates.preview)
async def process_preview_action(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    
    if action == "ok":
        # Переходим к настройке премодерации
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="mod_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="mod_no")]
        ])
        
        await call.message.edit_text(
            "Шаг 7: Включить премодерацию постов?\n\n"
            "При включенной премодерации каждый пост будет требовать вашего одобрения перед публикацией.",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.moderation)
    
    elif action == "regen":
        # Регенерируем пример
        user_data = await state.get_data()
        
        await call.message.edit_text("⏳ Генерируем новый пример поста...")
        
        try:
            # Формируем базовый промпт для другого примера
            content_type = user_data["content_type_name"]
            themes = user_data["themes"]
            tone = user_data["tone_name"]
            structure = user_data["structure"]
            
            structure_text = []
            if structure.get("title", False):
                structure_text.append("заголовок")
            if structure.get("main", False):
                structure_text.append("основной текст")
            if structure.get("quote", False):
                structure_text.append("выделенную цитату")
            if structure.get("conclusion", False):
                structure_text.append("заключение/вывод")
            if structure.get("hashtags", False):
                structure_text.append("хэштеги")
            
            length_text = user_data["length_name"].split(" ")[0].lower()
            
            # Формируем промпт для генерации другого примера
            prompt = (
                f"Создай {content_type} пост на тему '{themes}' в {tone} тоне, "
                f"отличающийся от предыдущего варианта. "
                f"Пост должен включать {', '.join(structure_text)}. "
                f"Длина поста: {length_text}. "
            )
            
            # Добавляем эмодзи если нужно
            if structure.get("emoji", False):
                prompt += " Добавь подходящие эмодзи для украшения текста."
            
            # Генерируем новый пример поста
            new_example_text = await generate_article(prompt)
            
            # Сохраняем новый пример поста
            await state.update_data(example_text=new_example_text)
            
            # Создаем клавиатуру для подтверждения
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Всё верно", callback_data="preview_ok")],
                [InlineKeyboardButton(text="🔄 Сгенерировать другой пример", callback_data="preview_regen")],
                [InlineKeyboardButton(text="⬅️ Вернуться к настройкам", callback_data="preview_back")]
            ])
            
            await call.message.edit_text(
                f"📝 Новый пример поста:\n\n"
                f"{new_example_text}\n\n"
                f"Вас устраивает этот формат?",
                reply_markup=markup
            )
        
        except Exception as e:
            logger.error(f"Error regenerating preview: {e}")
            await call.message.edit_text(
                f"❌ Не удалось сгенерировать новый пример поста.\n"
                f"Пожалуйста, попробуйте еще раз."
            )
            
            # Восстанавливаем клавиатуру
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Всё верно", callback_data="preview_ok")],
                [InlineKeyboardButton(text="🔄 Сгенерировать другой пример", callback_data="preview_regen")],
                [InlineKeyboardButton(text="⬅️ Вернуться к настройкам", callback_data="preview_back")]
            ])
            
            await call.message.edit_reply_markup(reply_markup=markup)
    
    elif action == "back":
        # Возвращаемся к началу настройки
        await start_auto_gen(call.message, state)


@router.callback_query(AutoGenStates.moderation)
async def process_moderation_choice(call: CallbackQuery, state: FSMContext):
    mod_enabled = call.data == "mod_yes"
    
    # Сохраняем выбор премодерации
    await state.update_data(moderation_enabled=mod_enabled)
    
    # Формируем сводку параметров
    user_data = await state.get_data()
    
    # Преобразуем структуру в текстовый формат
    selected_structure = [name for code, name in STRUCTURE_OPTIONS.items() 
                         if user_data["structure"].get(code, False)]
    structure_text = ", ".join(selected_structure)
    
    summary = (
        f"📋 Сводка настроек автогенерации:\n\n"
        f"📌 Тип контента: {user_data['content_type_name']}\n"
        f"📌 Темы: {user_data['themes']}\n"
        f"📌 Тон: {user_data['tone_name']}\n"
        f"📌 Структура: {structure_text}\n"
        f"📌 Длина: {user_data['length_name']}\n"
        f"📌 Количество постов: {user_data['post_count']}\n"
        f"📌 Премодерация: {'✅ Включена' if mod_enabled else '❌ Отключена'}\n\n"
        f"Пример поста:\n{user_data['example_text'][:200]}..."
    )
    
    # Клавиатура для подтверждения
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и запустить", callback_data="template_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="template_cancel")]
    ])
    
    await call.message.edit_text(
        f"{summary}\n\n"
        f"Запустить генерацию с этими параметрами?",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.confirmation)


@router.callback_query(AutoGenStates.confirmation)
async def process_final_confirmation(call: CallbackQuery, state: FSMContext):
    if call.data == "template_confirm":
        # Получаем данные из состояния
        user_data = await state.get_data()
        
        # Преобразуем структуру в JSON строку для сохранения в базе данных
        structure_json = json.dumps({k: v for k, v in user_data["structure"].items() if v})
        
        await call.message.edit_text(
            "✅ Параметры настроены!\n\n"
            "⏳ Начинаем генерацию постов. Это может занять некоторое время.\n"
            "Вы получите уведомление, когда посты будут готовы."
        )
        
        # Запускаем процесс генерации в фоне
        asyncio.create_task(
            generate_posts(
                chat_id=user_data.get("chat_id"),
                user_id=call.from_user.id,
                content_type=user_data["content_type_name"],
                themes=user_data["themes"],
                tone=user_data["tone_name"],
                structure=user_data["structure"],
                length=user_data["length_name"],
                post_count=user_data["post_count"],
                moderation_enabled=user_data["moderation_enabled"],
                bot=call.bot
            )
        )
        
        # Очищаем состояние
        await state.clear()
    
    else:  # template_cancel
        await call.message.edit_text(
            "❌ Настройка автогенерации отменена.\n"
            "Вы можете начать настройку заново или вернуться в главное меню."
        )
        await state.clear()


# Функция для генерации постов в фоновом режиме
async def generate_posts(
    chat_id: int, 
    user_id: int, 
    content_type: str,
    themes: str,
    tone: str,
    structure: dict,
    length: str,
    post_count: int,
    moderation_enabled: bool,
    bot
):
    """Асинхронная функция для генерации постов на основе параметров"""
    post_ids = []
    
    try:
        # Логируем начало процесса
        logger.info(f"Starting post generation for chat {chat_id}, user {user_id}")
        logger.info(f"Parameters: {content_type}, {themes}, {tone}, {post_count} posts")
        
        # Формируем базовый промпт
        structure_text = []
        if structure.get("title", False):
            structure_text.append("заголовок")
        if structure.get("main", False):
            structure_text.append("основной текст")
        if structure.get("quote", False):
            structure_text.append("выделенную цитату")
        if structure.get("conclusion", False):
            structure_text.append("заключение/вывод")
        if structure.get("hashtags", False):
            structure_text.append("хэштеги")
        
        # Определяем длину в символах
        length_map = {
            "short": "до 300 символов", 
            "medium": "300-800 символов", 
            "long": "800-1500 символов"
        }
        length_text = length_map.get(length.split(" ")[0].lower(), "300-800 символов")
        
        async with AsyncSessionLocal() as session:
            # Генерируем посты
            for i in range(post_count):
                try:
                    # Формируем уникальный промпт для каждого поста
                    prompt = (
                        f"Создай {content_type} пост на тему '{themes}' в {tone} тоне. "
                        f"Пост должен включать {', '.join(structure_text)}. "
                        f"Длина поста: {length_text}. "
                        f"Сделай контент уникальным и интересным. "
                        f"Это пост {i+1} из {post_count}, так что разнообразь содержание."
                    )
                    
                    # Добавляем эмодзи если нужно
                    if structure.get("emoji", False):
                        prompt += " Добавь подходящие эмодзи для украшения текста."
                    
                    # Генерируем контент
                    logger.info(f"Generating post {i+1}/{post_count}")
                    generated_text = await generate_article(prompt)
                    
                    # Сохраняем пост в базе данных
                    new_post = Post(
                        chat_id=chat_id,
                        text=generated_text,
                        media_file_id=None,  # Пока без медиа
                        publish_at=datetime.now(timezone.utc),  # По умолчанию текущее время
                        created_by=user_id,
                        status="pending" if moderation_enabled else "approved",
                        published=False,
                        is_generated=True,
                        generation_params=json.dumps({
                            "content_type": content_type,
                            "themes": themes,
                            "tone": tone,
                            "structure": structure,
                            "length": length
                        })
                    )
                    
                    session.add(new_post)
                    await session.flush()  # Чтобы получить ID
                    
                    post_ids.append(new_post.id)
                    logger.info(f"Post {i+1} generated with ID {new_post.id}")
                    
                    # Небольшая задержка чтобы не перегружать API
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"Error generating post {i+1}: {str(e)}")
            
            await session.commit()
        
        # Отправляем уведомление о завершении
        if post_ids:
            # Сообщение о завершении генерации
            completion_message = (
                f"✅ Генерация завершена! Создано постов: {len(post_ids)}\n\n"
            )
            
            # Добавляем инструкцию в зависимости от настроек модерации
            if moderation_enabled:
                completion_message += (
                    f"🔍 Посты требуют вашего одобрения перед публикацией.\n"
                    f"Перейдите в раздел '🕓 Ожидают публикации' для проверки."
                )
            else:
                completion_message += (
                    f"🚀 Посты добавлены в очередь на публикацию.\n"
                    f"Перейдите в раздел '📋 Очередь публикаций' для управления расписанием."
                )
            
            await bot.send_message(user_id, completion_message)
        else:
            await bot.send_message(
                user_id,
                "⚠️ Не удалось сгенерировать посты. Пожалуйста, попробуйте еще раз с другими параметрами."
            )
    
    except Exception as e:
        logger.error(f"Error in generate_posts: {str(e)}")
        # Отправляем сообщение об ошибке
        try:
            await bot.send_message(
                user_id,
                f"❌ Произошла ошибка при генерации постов: {str(e)}\n"
                f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
            )
        except:
            pass
