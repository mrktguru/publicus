# handlers/auto_generation.py
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
from database.models import Post, Group
from gpt_client import generate_article
from utils.prompt_manager import (
    PRO_MODE, BASIC_MODE, CONTENT_TYPES, TONES, STRUCTURE_OPTIONS, 
    LENGTH_OPTIONS, BLOG_TOPICS, validate_pro_prompt, build_basic_prompt
)

router = Router()
logger = logging.getLogger(__name__)

class AutoGenStates(StatesGroup):
    # Начальный выбор режима
    mode_selection = State()
    
    # Состояния для режима BASIC
    blog_topic = State()  # Новое состояние для выбора тематики блога
    content_type = State()
    themes = State()
    tone = State()
    structure = State()
    length = State()
    post_count = State()
    preview = State()
    moderation = State()
    confirmation = State()
    
    # Состояния для режима PRO
    pro_prompt = State()
    pro_preview = State()
    pro_post_count = State()
    pro_moderation = State()
    pro_confirmation = State()


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
    
    # Создаем клавиатуру для выбора режима
    kb = [
        [InlineKeyboardButton(text="🔧 Конструктор (BASIC)", callback_data="mode_basic")],
        [InlineKeyboardButton(text="📝 Свой промпт (PRO)", callback_data="mode_pro")]
    ]
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await message.answer(
        "Выберите режим создания контента:\n\n"
        "🔧 <b>Конструктор (BASIC)</b> - пошаговая настройка параметров\n\n"
        "📝 <b>Свой промпт (PRO)</b> - напишите промпт самостоятельно",
        reply_markup=markup,
        parse_mode="HTML"
    )
    
    await state.set_state(AutoGenStates.mode_selection)


@router.callback_query(AutoGenStates.mode_selection)
async def process_mode_selection(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора режима автогенерации"""
    mode = call.data.split("_")[1]
    
    if mode == "basic":
        # Начинаем с выбора тематики блога в режиме BASIC
        kb = []
        for code, name in BLOG_TOPICS.items():
            kb.append([InlineKeyboardButton(text=name, callback_data=f"blog_{code}")])
        
        markup = InlineKeyboardMarkup(inline_keyboard=kb)
        
        await call.message.edit_text(
            "Выбран режим <b>Конструктор (BASIC)</b>\n\n"
            "Шаг 1: Выберите основную тематику блога:",
            parse_mode="HTML",
            reply_markup=markup
        )
        await state.set_state(AutoGenStates.blog_topic)
        
    elif mode == "pro":
        await call.message.edit_text(
            "Выбран режим <b>Свой промпт (PRO)</b>\n\n"
            "Напишите свой промпт для генерации контента:\n\n"
            "Примеры эффективных промптов:\n"
            "- \"Напиши статью о преимуществах электромобилей с акцентом на экологию\"\n"
            "- \"Создай пост с тремя малоизвестными фактами о космосе\"\n"
            "- \"Сравни iPhone и Android с точки зрения пользовательского опыта\"\n\n"
            "<i>Напишите свой промпт в ответном сообщении</i>",
            parse_mode="HTML"
        )
        await state.set_state(AutoGenStates.pro_prompt)


# ------------------ BASIC MODE HANDLERS ------------------

@router.callback_query(AutoGenStates.blog_topic, F.data.startswith("blog_"))
async def process_blog_topic(call: CallbackQuery, state: FSMContext):
    """Обработка выбора тематики блога"""
    blog_topic_code = call.data.split("_")[1]
    blog_topic_name = BLOG_TOPICS[blog_topic_code]
    
    # Сохраняем выбор
    await state.update_data(blog_topic_code=blog_topic_code, blog_topic_name=blog_topic_name)
    
    # Переходим к выбору типа контента
    kb = []
    for code, name in CONTENT_TYPES.items():
        kb.append([InlineKeyboardButton(text=name, callback_data=f"ct_{code}")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await call.message.edit_text(
        f"✅ Выбрана тематика: {blog_topic_name}\n\n"
        f"Шаг 2: Выберите тип контента для генерации:",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.content_type)


@router.callback_query(AutoGenStates.content_type, F.data.startswith("ct_"))
async def process_content_type(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа контента"""
    content_type_code = call.data.split("_")[1]
    content_type_name = CONTENT_TYPES[content_type_code]
    
    # Сохраняем выбор в состоянии
    await state.update_data(content_type_code=content_type_code, content_type_name=content_type_name)
    
    user_data = await state.get_data()
    blog_topic_name = user_data.get("blog_topic_name", "")
    
    await call.message.edit_text(
        f"✅ Выбран тип контента: {content_type_name}\n\n"
        f"Шаг 3: Введите конкретную тему поста для {blog_topic_name}:\n\n"
        f"Например: Новейшие технологии в области искусственного интеллекта"
    )
    
    await state.set_state(AutoGenStates.themes)


@router.message(AutoGenStates.themes)
async def process_themes(message: Message, state: FSMContext):
    """Обработка ввода темы поста"""
    themes = message.text.strip()
    
    # Сохраняем темы
    await state.update_data(themes=themes)
    
    # Создаем клавиатуру для выбора тона
    kb = []
    for code, name in TONES.items():
        kb.append([InlineKeyboardButton(text=name, callback_data=f"tone_{code}")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await message.answer(
        f"✅ Тема сохранена: {themes}\n\n"
        f"Шаг 4: Выберите тон повествования:",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.tone)


@router.callback_query(AutoGenStates.tone, F.data.startswith("tone_"))
async def process_tone(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора тона повествования"""
    tone_code = call.data.split("_")[1]
    tone_name = TONES[tone_code]
    
    # Сохраняем тон
    await state.update_data(tone_code=tone_code, tone_name=tone_name)
    
    # Создаем клавиатуру для структуры (множественный выбор)
    structure_kb = []
    
    # Получаем текущую структуру (если уже выбирали)
    user_data = await state.get_data()
    structure = user_data.get("structure", {"main": True})
    
    for code, name in STRUCTURE_OPTIONS.items():
        # По умолчанию выбираем основной текст
        is_selected = structure.get(code, code == "main")
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
        f"Шаг 5: Выберите компоненты структуры поста (можно выбрать несколько):",
        reply_markup=markup
    )
    
    # Инициализируем структуру если ее еще нет
    if "structure" not in user_data:
        await state.update_data(structure={"main": True})
    
    await state.set_state(AutoGenStates.structure)


@router.callback_query(AutoGenStates.structure, F.data.startswith("struct_"))
async def process_structure_selection(call: CallbackQuery, state: FSMContext):
    """Обработчик выбора элементов структуры"""
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
            f"Шаг 6: Выберите предпочтительную длину поста:",
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
    """Обработчик выбора длины поста"""
    length_code = call.data.split("_")[1]
    length_name = LENGTH_OPTIONS[length_code]
    
    # Сохраняем длину
    await state.update_data(length_code=length_code, length_name=length_name)
    
    await call.message.edit_text(
        f"✅ Выбрана длина: {length_name}\n\n"
        f"Шаг 7: Введите количество постов для генерации (от 1 до 30):"
    )
    
    await state.set_state(AutoGenStates.post_count)


@router.message(AutoGenStates.post_count)
async def process_post_count(message: Message, state: FSMContext):
    """Обработка ввода количества постов"""
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
    
    try:
        # Формируем промпт по параметрам
        prompt = build_basic_prompt(user_data)
        
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
    """Обработка действий с предпросмотром"""
    action = call.data.split("_")[1]
    
    if action == "ok":
        # Переходим к настройке премодерации
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="mod_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="mod_no")]
        ])
        
        await call.message.edit_text(
            "Шаг 8: Включить премодерацию постов?\n\n"
            "При включенной премодерации каждый пост будет требовать вашего одобрения перед публикацией.",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.moderation)
    
    elif action == "regen":
        # Регенерируем пример
        user_data = await state.get_data()
        
        await call.message.edit_text("⏳ Генерируем новый пример поста...")
        
        try:
            # Формируем промпт по параметрам
            prompt = build_basic_prompt(user_data)
            
            # Добавляем указание на другой вариант
            prompt += " Создай другой вариант поста, отличающийся от предыдущего."
            
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
    """Обработка выбора премодерации"""
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
        f"📌 Тематика блога: {user_data['blog_topic_name']}\n"
        f"📌 Тип контента: {user_data['content_type_name']}\n"
        f"📌 Тема: {user_data['themes']}\n"
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
    """Обработка финального подтверждения BASIC режима"""
    if call.data == "template_confirm":
        # Получаем данные из состояния
        user_data = await state.get_data()
        
        await call.message.edit_text(
            "✅ Параметры настроены!\n\n"
            "⏳ Начинаем генерацию постов. Это может занять некоторое время.\n"
            "Вы получите уведомление, когда посты будут готовы."
        )
        
        # Запускаем процесс генерации в фоне
        asyncio.create_task(
            generate_posts_with_basic_prompt(
                chat_id=user_data.get("chat_id"),
                user_id=call

@router.callback_query(AutoGenStates.confirmation)
async def process_final_confirmation(call: CallbackQuery, state: FSMContext):
    """Обработка финального подтверждения BASIC режима"""
    if call.data == "template_confirm":
        # Получаем данные из состояния
        user_data = await state.get_data()
        
        await call.message.edit_text(
            "✅ Параметры настроены!\n\n"
            "⏳ Начинаем генерацию постов. Это может занять некоторое время.\n"
            "Вы получите уведомление, когда посты будут готовы."
        )
        
        # Запускаем процесс генерации в фоне
        asyncio.create_task(
            generate_posts_with_basic_prompt(
                chat_id=user_data.get("chat_id"),
                user_id=call.from_user.id,
                params=user_data,
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


# ------------------ PRO MODE HANDLERS ------------------

@router.message(AutoGenStates.pro_prompt)
async def process_pro_prompt(message: Message, state: FSMContext):
    """Обработка ввода промпта в режиме PRO"""
    prompt_text = message.text.strip()
    
    # Проверка промпта
    if not validate_pro_prompt(prompt_text):
        await message.answer(
            "❌ Ваш промпт слишком длинный или содержит запрещенные слова.\n"
            f"Максимальная длина: {MAX_PROMPT_LENGTH} символов.\n\n"
            "Пожалуйста, отредактируйте промпт и отправьте снова:"
        )
        return
    
    # Сохраняем промпт
    await state.update_data(pro_prompt=prompt_text)
    
    # Запрос количества постов
    await message.answer(
        "✅ Промпт принят!\n\n"
        "Сколько постов вы хотите сгенерировать? (от 1 до 30):"
    )
    
    await state.set_state(AutoGenStates.pro_post_count)


@router.message(AutoGenStates.pro_post_count)
async def process_pro_post_count(message: Message, state: FSMContext):
    """Обработка ввода количества постов для PRO режима"""
    try:
        count = int(message.text.strip())
        if count < 1:
            count = 1
        elif count > 30:
            count = 30
    except ValueError:
        count = 1  # По умолчанию
    
    # Сохраняем количество
    await state.update_data(post_count=count)
    
    # Генерируем пример поста
    user_data = await state.get_data()
    pro_prompt = user_data.get("pro_prompt", "")
    
    await message.answer("⏳ Генерируем пример поста на основе вашего промпта...")
    
    try:
        # Генерируем пример
        example_text = await generate_article(pro_prompt)
        
        # Сохраняем пример
        await state.update_data(example_text=example_text)
        
        # Кнопки для выбора действия
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Всё верно", callback_data="pro_preview_ok")],
            [InlineKeyboardButton(text="🔄 Сгенерировать другой", callback_data="pro_preview_regen")],
            [InlineKeyboardButton(text="📝 Изменить промпт", callback_data="pro_preview_edit")]
        ])
        
        await message.answer(
            f"📝 Пример поста на основе вашего промпта:\n\n"
            f"{example_text}\n\n"
            f"Вас устраивает этот результат?",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.pro_preview)
        
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        await message.answer(
            "❌ Не удалось сгенерировать пример поста.\n"
            "Пожалуйста, попробуйте другой промпт или обратитесь к администратору."
        )
        await state.set_state(AutoGenStates.pro_prompt)


@router.callback_query(AutoGenStates.pro_preview)
async def process_pro_preview_action(call: CallbackQuery, state: FSMContext):
    """Обработка действий с предпросмотром в PRO режиме"""
    action = call.data.split("_")[2]
    
    if action == "ok":
        # Настройка премодерации
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="pro_mod_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="pro_mod_no")]
        ])
        
        await call.message.edit_text(
            "Включить премодерацию постов?\n\n"
            "При включенной премодерации каждый пост будет требовать вашего одобрения перед публикацией.",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.pro_moderation)
        
    elif action == "regen":
        # Регенерируем пример
        user_data = await state.get_data()
        pro_prompt = user_data.get("pro_prompt", "")
        
        await call.message.edit_text("⏳ Генерируем новый пример поста...")
        
        try:
            # Генерируем новый пример
            new_example = await generate_article(pro_prompt)
            
            # Сохраняем новый пример
            await state.update_data(example_text=new_example)
            
            # Обновляем сообщение
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Всё верно", callback_data="pro_preview_ok")],
                [InlineKeyboardButton(text="🔄 Сгенерировать другой", callback_data="pro_preview_regen")],
                [InlineKeyboardButton(text="📝 Изменить промпт", callback_data="pro_preview_edit")]
            ])
            
            await call.message.edit_text(
                f"📝 Новый пример поста:\n\n"
                f"{new_example}\n\n"
                f"Вас устраивает этот результат?",
                reply_markup=markup
            )
            
        except Exception as e:
            logger.error(f"Error regenerating preview: {e}")
            await call.message.edit_text(
                "❌ Не удалось сгенерировать новый пример поста.\n"
                "Пожалуйста, попробуйте другой промпт или обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Изменить промпт", callback_data="pro_preview_edit")]
                ])
            )
            
    elif action == "edit":
        # Возврат к редактированию промпта
        user_data = await state.get_data()
        old_prompt = user_data.get("pro_prompt", "")
        
        await call.message.edit_text(
            "Отредактируйте свой промпт и отправьте снова:\n\n"
            f"Текущий промпт:\n{old_prompt}"
        )
        
        await state.set_state(AutoGenStates.pro_prompt)


@router.callback_query(AutoGenStates.pro_moderation)
async def process_pro_moderation_choice(call: CallbackQuery, state: FSMContext):
    """Обработка выбора премодерации в PRO режиме"""
    mod_enabled = call.data == "pro_mod_yes"
    
    # Сохраняем выбор премодерации
    await state.update_data(moderation_enabled=mod_enabled)
    
    # Формируем сводку параметров
    user_data = await state.get_data()
    
    summary = (
        f"📋 Сводка настроек:\n\n"
        f"📌 Режим: PRO (свой промпт)\n"
        f"📌 Промпт: {user_data.get('pro_prompt', '')[:100]}...\n"
        f"📌 Количество постов: {user_data.get('post_count', 1)}\n"
        f"📌 Премодерация: {'✅ Включена' if mod_enabled else '❌ Отключена'}\n\n"
        f"Пример поста:\n{user_data.get('example_text', '')[:200]}..."
    )
    
    # Клавиатура для подтверждения
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и запустить", callback_data="pro_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="pro_cancel")]
    ])
    
    await call.message.edit_text(
        f"{summary}\n\n"
        f"Запустить генерацию с этими параметрами?",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.pro_confirmation)


@router.callback_query(AutoGenStates.pro_confirmation)
async def process_pro_final_confirmation(call: CallbackQuery, state: FSMContext):
    """Обработка финального подтверждения PRO режима"""
    if call.data == "pro_confirm":
        # Получаем данные из состояния
        user_data = await state.get_data()
        
        await call.message.edit_text(
            "✅ Параметры настроены!\n\n"
            "⏳ Начинаем генерацию постов. Это может занять некоторое время.\n"
            "Вы получите уведомление, когда посты будут готовы."
        )
        
        # Запускаем процесс генерации в фоне
        asyncio.create_task(
            generate_posts_with_pro_prompt(
                chat_id=user_data.get("chat_id"),
                user_id=call.from_user.id,
                prompt=user_data.get("pro_prompt", ""),
                post_count=user_data.get("post_count", 1),
                moderation_enabled=user_data.get("moderation_enabled", True),
                bot=call.bot
            )
        )
        
        # Очищаем состояние
        await state.clear()
    
    else:  # pro_cancel
        await call.message.edit_text(
            "❌ Настройка автогенерации отменена.\n"
            "Вы можете начать настройку заново или вернуться в главное меню."
        )
        await state.clear()


# ------------------ ФУНКЦИИ ГЕНЕРАЦИИ ------------------

async def generate_posts_with_basic_prompt(
    chat_id: int, 
    user_id: int, 
    params: dict,
    post_count: int,
    moderation_enabled: bool,
    bot
):
    """Генерирует посты с использованием параметров из конструктора BASIC"""
    post_ids = []
    
    try:
        # Логируем начало процесса
        logger.info(f"Starting post generation for chat {chat_id}, user {user_id}")
        logger.info(f"Parameters: {params}")
        
        async with AsyncSessionLocal() as session:
            # Генерируем посты
            for i in range(post_count):
                try:
                    # Формируем промпт на основе параметров
                    base_prompt = build_basic_prompt(params)
                    
                    # Добавляем указание на порядковый номер для разнообразия
                    if post_count > 1:
                        prompt = f"{base_prompt} (Это пост {i+1} из {post_count}, создай уникальный контент.)"
                    else:
                        prompt = base_prompt
                    
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
                            "mode": "BASIC",
                            "blog_topic": params.get("blog_topic_name"),
                            "content_type": params.get("content_type_name"),
                            "themes": params.get("themes"),
                            "tone": params.get("tone_name"),
                            "structure": {k: v for k, v in params.get("structure", {}).items() if v},
                            "length": params.get("length_name")
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
        logger.error(f"Error in generate_posts_with_basic_prompt: {str(e)}")
        # Отправляем сообщение об ошибке
        try:
            await bot.send_message(
                user_id,
                f"❌ Произошла ошибка при генерации постов: {str(e)}\n"
                f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
            )
        except Exception:
            pass


async def generate_posts_with_pro_prompt(
    chat_id: int, 
    user_id: int, 
    prompt: str,
    post_count: int,
    moderation_enabled: bool,
    bot
):
    """Генерирует посты с использованием пользовательского промпта из PRO режима"""
    post_ids = []
    
    try:
        # Логируем начало процесса
        logger.info(f"Starting post generation (PRO mode) for chat {chat_id}, user {user_id}")
        logger.info(f"Prompt: {prompt}")
        
        async with AsyncSessionLocal() as session:
            # Генерируем посты
            for i in range(post_count):
                try:
                    # Используем исходный промпт пользователя
                    current_prompt = prompt
                    
                    # Если нужно несколько постов, добавляем указание на порядковый номер
                    if post_count > 1:
                        current_prompt = f"{prompt} (Это пост {i+1} из {post_count}, создай уникальный контент.)"
                    
                    # Генерируем контент
                    logger.info(f"Generating post {i+1}/{post_count} (PRO mode)")
                    generated_text = await generate_article(current_prompt)
                    
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
                            "mode": "PRO",
                            "prompt": prompt
                        })
                    )
                    
                    session.add(new_post)
                    await session.flush()  # Чтобы получить ID
                    
                    post_ids.append(new_post.id)
                    logger.info(f"Post {i+1} (PRO mode) generated with ID {new_post.id}")
                    
                    # Небольшая задержка чтобы не перегружать API
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"Error generating post {i+1} (PRO mode): {str(e)}")
            
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
                "⚠️ Не удалось сгенерировать посты. Пожалуйста, попробуйте еще раз с другим промптом."
            )
    
    except Exception as e:
        logger.error(f"Error in generate_posts_with_pro_prompt: {str(e)}")
        # Отправляем сообщение об ошибке
        try:
            await bot.send_message(
                user_id,
                f"❌ Произошла ошибка при генерации постов: {str(e)}\n"
                f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
            )
        except Exception:
            pass


# Вспомогательные функции для создания клавиатур
def get_content_types_keyboard():
    """Создает клавиатуру с типами контента"""
    kb = []
    for code, name in CONTENT_TYPES.items():
        kb.append([InlineKeyboardButton(text=name, callback_data=f"ct_{code}")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

