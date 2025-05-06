# handlers/auto_generation.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
from datetime import datetime, timezone, timedelta
import logging
from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import Post, Group
from gpt_client import generate_article
from utils.prompt_manager import (
    PRO_MODE, BASIC_MODE, CONTENT_TYPES, TONES, STRUCTURE_OPTIONS, 
    LENGTH_OPTIONS, BLOG_TOPICS, validate_pro_prompt, build_basic_prompt,
    MAX_PROMPT_LENGTH
)

router = Router()
logger = logging.getLogger(__name__)

class AutoGenStates(StatesGroup):
    # Начальный выбор режима
    mode_selection = State()
    
    # Состояния для режима BASIC
    blog_topic = State()
    content_type = State()
    themes = State()
    tone = State()
    structure = State()
    length = State()
    generated_post = State()  # Новое состояние - результат генерации
    
    # Состояния для режима PRO
    pro_prompt = State()
    pro_generated_post = State()  # Новое состояние - результат генерации для PRO
    
    # Общие состояния для работы с постом
    edit_post = State()
    schedule_post = State()
    schedule_time = State()
    schedule_date = State()


@router.message(lambda m: m.text and m.text.startswith("🤖 Автогенерация постов"))
async def start_auto_gen(message: Message, state: FSMContext):
    """Начальный обработчик для генерации поста с помощью ИИ"""
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
    """Обработчик выбора режима генерации"""
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
    
    await call.message.edit_text("⏳ Генерируем пост на основе выбранных параметров...")
    
    # Генерируем пост
    user_data = await state.get_data()
    
    try:
        # Формируем промпт по параметрам
        prompt = build_basic_prompt(user_data)
        
        # Генерируем пост
        generated_text = await generate_article(prompt)
        
        # Сохраняем сгенерированный текст
        await state.update_data(generated_text=generated_text, generation_mode="BASIC")
        
        # Показываем результат с кнопками действий
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
            [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit")],
            [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
            [InlineKeyboardButton(text="🔧 Изменить параметры", callback_data="post_change_params")]
        ])
        
        await call.message.edit_text(
            f"✅ Пост сгенерирован!\n\n"
            f"{generated_text}\n\n"
            f"Выберите действие:",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.generated_post)
        
    except Exception as e:
        logger.error(f"Error generating post: {str(e)}")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="regenerate_basic")],
            [InlineKeyboardButton(text="⬅️ Вернуться к параметрам", callback_data="back_to_params")]
        ])
        
        await call.message.edit_text(
            f"❌ Произошла ошибка при генерации поста: {str(e)}\n\n"
            f"Что делать дальше?",
            reply_markup=markup
        )
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
    
    await message.answer("⏳ Генерируем пост на основе вашего промпта...")
    
    try:
        # Генерируем пример
        generated_text = await generate_article(prompt_text)
        
        # Сохраняем сгенерированный текст
        await state.update_data(generated_text=generated_text, generation_mode="PRO")
        
        # Показываем результат с кнопками действий
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
            [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit")],
            [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
            [InlineKeyboardButton(text="📝 Изменить промпт", callback_data="post_change_prompt")]
        ])
        
        await message.answer(
            f"✅ Пост сгенерирован!\n\n"
            f"{generated_text}\n\n"
            f"Выберите действие:",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.pro_generated_post)
        
    except Exception as e:
        logger.error(f"Error generating post in PRO mode: {str(e)}")
        await message.answer(
            f"❌ Произошла ошибка при генерации поста: {str(e)}\n\n"
            f"Пожалуйста, попробуйте другой промпт или обратитесь к администратору."
        )
        await state.set_state(AutoGenStates.pro_prompt)
# ------------------ ОБЩИЕ ДЕЙСТВИЯ С ПОСТОМ ------------------

# Обработка действий с сгенерированным постом в режиме BASIC
@router.callback_query(AutoGenStates.generated_post)
async def process_post_action_basic(call: CallbackQuery, state: FSMContext):
    await process_post_action(call, state)


# Обработка действий с сгенерированным постом в режиме PRO
@router.callback_query(AutoGenStates.pro_generated_post)
async def process_post_action_pro(call: CallbackQuery, state: FSMContext):
    await process_post_action(call, state)


async def process_post_action(call: CallbackQuery, state: FSMContext):
    """Обработчик действий с сгенерированным постом"""
    action = call.data.split("_", 1)[1]
    user_data = await state.get_data()
    generation_mode = user_data.get("generation_mode", "BASIC")
    
    if action == "publish_now":
        # Публикуем пост прямо сейчас
        await publish_post_now(call, state)
        
    elif action == "schedule":
        # Запрашиваем дату публикации
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data=f"date_{today.isoformat()}")],
            [InlineKeyboardButton(text="Завтра", callback_data=f"date_{tomorrow.isoformat()}")],
            [InlineKeyboardButton(text="Послезавтра", callback_data=f"date_{day_after.isoformat()}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_post")]
        ])
        
        await call.message.edit_text(
            "📆 Выберите дату публикации:",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.schedule_date)
    elif action == "edit":
        # Отправляем текст для редактирования с инструкциями
        await call.message.edit_text(
            "✏️ <b>Редактирование поста</b>\n\n"
            "Текущий текст поста:\n"
            f"{user_data.get('generated_text', '')}\n\n"
            "📝 <b>Отправьте отредактированный текст в следующем сообщении.</b>\n\n"
            "Вы можете использовать форматирование Telegram:\n"
            "- *жирный текст* (между звездочками)\n"
            "- _курсив_ (между нижними подчеркиваниями)\n"
            "- `код` (между обратными кавычками)\n"
            "- [текст ссылки](URL) (ссылки)",
            parse_mode="HTML"
        )
        
        await state.set_state(AutoGenStates.edit_post)
        
    elif action == "regenerate":
        # Регенерируем пост
        await call.message.edit_text("⏳ Генерируем новый вариант поста...")
        
        try:
            if generation_mode == "BASIC":
                # Для BASIC используем построенный промпт
                prompt = build_basic_prompt(user_data)
                prompt += " Создай совершенно другой вариант поста."
            else:
                # Для PRO используем готовый промпт
                prompt = user_data.get("pro_prompt", "")
                prompt += " Создай совершенно другой вариант."
            
            # Генерируем новый пост
            generated_text = await generate_article(prompt)
            
            # Сохраняем новый текст
            await state.update_data(generated_text=generated_text)
            
            # Показываем новый пост с кнопками
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
                [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
                [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit")],
                [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
                [InlineKeyboardButton(
                    text="🔧 Изменить параметры" if generation_mode == "BASIC" else "📝 Изменить промпт",
                    callback_data="post_change_params" if generation_mode == "BASIC" else "post_change_prompt"
                )]
            ])
            
            await call.message.edit_text(
                f"✅ Новый пост сгенерирован!\n\n"
                f"{generated_text}\n\n"
                f"Выберите действие:",
                reply_markup=markup
            )
            
        except Exception as e:
            logger.error(f"Error regenerating post: {str(e)}")
            
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="post_regenerate")],
                [InlineKeyboardButton(text="⬅️ Назад к посту", callback_data="back_to_post")]
            ])
            
            await call.message.edit_text(
                f"❌ Произошла ошибка при генерации нового варианта: {str(e)}\n\n"
                f"Что делать дальше?",
                reply_markup=markup
            )
    elif action == "change_params":
        # Возвращаемся к выбору параметров в режиме BASIC
        await call.message.edit_text(
            "🔄 Возвращаемся к настройке параметров..."
        )
        
        # Возвращаемся к первому шагу BASIC
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
    
    elif action == "change_prompt":
        # Возвращаемся к вводу промпта в режиме PRO
        old_prompt = user_data.get("pro_prompt", "")
        
        await call.message.edit_text(
            "Выбран режим <b>Свой промпт (PRO)</b>\n\n"
            "Измените промпт и отправьте его снова:\n\n"
            f"<b>Текущий промпт:</b>\n{old_prompt}\n\n"
            "<i>Напишите новый промпт в ответном сообщении</i>",
            parse_mode="HTML"
        )
        await state.set_state(AutoGenStates.pro_prompt)


@router.message(AutoGenStates.edit_post)
async def process_edited_post(message: Message, state: FSMContext):
    """Обработка отредактированного поста"""
    edited_text = message.text.strip()
    
    if not edited_text:
        await message.answer(
            "❌ Текст поста не может быть пустым. Пожалуйста, введите текст:"
        )
        return
    
    # Сохраняем отредактированный текст
    await state.update_data(generated_text=edited_text)
    user_data = await state.get_data()
    generation_mode = user_data.get("generation_mode", "BASIC")
    
    # Показываем отредактированный пост с кнопками действий
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
        [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
        [InlineKeyboardButton(text="✏️ Редактировать еще", callback_data="post_edit")],
        [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
        [InlineKeyboardButton(
            text="🔧 Изменить параметры" if generation_mode == "BASIC" else "📝 Изменить промпт",
            callback_data="post_change_params" if generation_mode == "BASIC" else "post_change_prompt"
        )]
    ])
    
    await message.answer(
        f"✅ Пост отредактирован!\n\n"
        f"{edited_text}\n\n"
        f"Выберите действие:",
        reply_markup=markup,
        parse_mode="HTML"  # Поддержка форматирования в отредактированном тексте
    )
    
    # Возвращаемся к соответствующему состоянию в зависимости от режима
    if generation_mode == "BASIC":
        await state.set_state(AutoGenStates.generated_post)
    else:
        await state.set_state(AutoGenStates.pro_generated_post)
@router.callback_query(AutoGenStates.schedule_date)
async def process_schedule_date(call: CallbackQuery, state: FSMContext):
    """Обработка выбора даты для планирования публикации"""
    if call.data == "back_to_post":
        # Возвращаемся к посту
        user_data = await state.get_data()
        generation_mode = user_data.get("generation_mode", "BASIC")
        generated_text = user_data.get("generated_text", "")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
            [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit")],
            [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
            [InlineKeyboardButton(
                text="🔧 Изменить параметры" if generation_mode == "BASIC" else "📝 Изменить промпт",
                callback_data="post_change_params" if generation_mode == "BASIC" else "post_change_prompt"
            )]
        ])
        
        await call.message.edit_text(
            f"Сгенерированный пост:\n\n"
            f"{generated_text}\n\n"
            f"Выберите действие:",
            reply_markup=markup
        )
        
        # Возвращаемся к соответствующему состоянию
        if generation_mode == "BASIC":
            await state.set_state(AutoGenStates.generated_post)
        else:
            await state.set_state(AutoGenStates.pro_generated_post)
        
        return
    
    # Обрабатываем выбор даты
    date_str = call.data.split("_")[1]
    selected_date = datetime.fromisoformat(date_str).date()
    
    # Сохраняем выбранную дату
    await state.update_data(selected_date=date_str)
    
    # Предлагаем выбрать время
    current_hour = datetime.now().hour
    
    # Создаем кнопки для выбора времени с шагом в 1 час
    time_kb = []
    for hour in range(current_hour, current_hour + 12):
        actual_hour = hour % 24
        time_kb.append([
            InlineKeyboardButton(
                text=f"{actual_hour:02d}:00", 
                callback_data=f"time_{actual_hour:02d}00"
            ),
            InlineKeyboardButton(
                text=f"{actual_hour:02d}:30", 
                callback_data=f"time_{actual_hour:02d}30"
            )
        ])
    
    time_kb.append([InlineKeyboardButton(text="⬅️ Назад к выбору даты", callback_data="back_to_date")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=time_kb)
    
    await call.message.edit_text(
        f"📆 Выбрана дата: {selected_date.strftime('%d.%m.%Y')}\n\n"
        f"⏰ Выберите время публикации:",
        reply_markup=markup
    )
    
    await state.set_state(AutoGenStates.schedule_time)


@router.callback_query(AutoGenStates.schedule_time)
async def process_schedule_time(call: CallbackQuery, state: FSMContext):
    """Обработка выбора времени для планирования публикации"""
    if call.data == "back_to_date":
        # Возвращаемся к выбору даты
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data=f"date_{today.isoformat()}")],
            [InlineKeyboardButton(text="Завтра", callback_data=f"date_{tomorrow.isoformat()}")],
            [InlineKeyboardButton(text="Послезавтра", callback_data=f"date_{day_after.isoformat()}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_post")]
        ])
        
        await call.message.edit_text(
            "📆 Выберите дату публикации:",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.schedule_date)
        return
    
    # Обрабатываем выбор времени
    time_str = call.data.split("_")[1]
    hour = int(time_str[:2])
    minute = int(time_str[2:])
    
    user_data = await state.get_data()
    date_str = user_data.get("selected_date")
    selected_date = datetime.fromisoformat(date_str).date()
    
    # Создаем полную дату и время публикации
    publish_datetime = datetime.combine(
        selected_date, 
        datetime.min.time().replace(hour=hour, minute=minute)
    )
    
    # Сохраняем сгенерированный пост в БД с запланированной датой
    generated_text = user_data.get("generated_text", "")
    chat_id = user_data.get("chat_id")
    user_id = call.from_user.id
    generation_mode = user_data.get("generation_mode", "BASIC")
    
    # Сохраняем параметры генерации в зависимости от режима
    if generation_mode == "BASIC":
        generation_params = {
            "mode": "BASIC",
            "blog_topic": user_data.get("blog_topic_name"),
            "content_type": user_data.get("content_type_name"),
            "themes": user_data.get("themes"),
            "tone": user_data.get("tone_name"),
            "structure": {k: v for k, v in user_data.get("structure", {}).items() if v},
            "length": user_data.get("length_name")
        }
    else:
        generation_params = {
            "mode": "PRO",
            "prompt": user_data.get("pro_prompt", "")
        }
    
    try:
        async with AsyncSessionLocal() as session:
            # Создаем новую запись в БД
            post = Post(
                chat_id=chat_id,
                text=generated_text,
                publish_at=publish_datetime,
                created_by=user_id,
                status="approved",
                published=False,
                is_generated=True,
                generation_params=json.dumps(generation_params)
            )
            
            session.add(post)
            await session.commit()
            
            # Оповещаем пользователя об успешном планировании
            await call.message.edit_text(
                f"✅ Пост запланирован на {publish_datetime.strftime('%d.%m.%Y %H:%M')}!\n\n"
                f"{generated_text[:200]}...\n\n"
                f"Пост будет автоматически опубликован в указанное время.\n"
                f"Вы можете управлять запланированными постами в разделе '📋 Очередь публикаций'"
            )
            
            # Очищаем состояние
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error scheduling post: {e}")
        
        await call.message.edit_text(
            f"❌ Ошибка при планировании публикации: {str(e)}\n\n"
            f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
        )


async def publish_post_now(call: CallbackQuery, state: FSMContext):
    """Функция для немедленной публикации поста"""
    user_data = await state.get_data()
    generated_text = user_data.get("generated_text", "")
    chat_id = user_data.get("chat_id")
    generation_mode = user_data.get("generation_mode", "BASIC")
    
    # Сохраняем параметры генерации в зависимости от режима
    if generation_mode == "BASIC":
        generation_params = {
            "mode": "BASIC",
            "blog_topic": user_data.get("blog_topic_name"),
            "content_type": user_data.get("content_type_name"),
            "themes": user_data.get("themes"),
            "tone": user_data.get("tone_name"),
            "structure": {k: v for k, v in user_data.get("structure", {}).items() if v},
            "length": user_data.get("length_name")
        }
    else:
        generation_params = {
            "mode": "PRO",
            "prompt": user_data.get("pro_prompt", "")
        }
    
    try:
        # Отправляем сообщение в чат
        await call.bot.send_message(
            chat_id=chat_id,
            text=generated_text,
            parse_mode="HTML"
        )
        
        # Сохраняем пост в БД как опубликованный
        async with AsyncSessionLocal() as session:
            post = Post(
                chat_id=chat_id,
                text=generated_text,
                publish_at=datetime.now(timezone.utc),
                created_by=call.from_user.id,
                status="approved",
                published=True,
                is_generated=True,
                generation_params=json.dumps(generation_params)
            )
            
            session.add(post)
            await session.commit()
            
        # Оповещаем пользователя об успешной публикации
        await call.message.edit_text(
            "✅ Пост успешно опубликован!\n\n"
            f"{generated_text[:200]}...\n\n"
            "Для создания нового поста воспользуйтесь командой '✨ Создать пост' в главном меню."
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error publishing post: {str(e)}")
        
        await call.message.edit_text(
            f"❌ Ошибка при публикации поста: {str(e)}\n\n"
            f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
        )


# Обработчики для навигации между состояниями
@router.callback_query(lambda c: c.data == "regenerate_basic")
async def regenerate_basic_post(call: CallbackQuery, state: FSMContext):
    """Обработчик повторной генерации поста в режиме BASIC"""
    user_data = await state.get_data()
    
    await call.message.edit_text("⏳ Генерируем пост на основе выбранных параметров...")
    
    try:
        # Формируем промпт по параметрам
        prompt = build_basic_prompt(user_data)
        
        # Генерируем пост
        generated_text = await generate_article(prompt)
        
        # Сохраняем сгенерированный текст
        await state.update_data(generated_text=generated_text, generation_mode="BASIC")
        
        # Показываем результат с кнопками действий
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
            [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit")],
            [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
            [InlineKeyboardButton(text="🔧 Изменить параметры", callback_data="post_change_params")]
        ])
        
        await call.message.edit_text(
            f"✅ Пост сгенерирован!\n\n"
            f"{generated_text}\n\n"
            f"Выберите действие:",
            reply_markup=markup
        )
        
        await state.set_state(AutoGenStates.generated_post)
        
    except Exception as e:
        logger.error(f"Error regenerating post: {str(e)}")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="regenerate_basic")],
            [InlineKeyboardButton(text="⬅️ Вернуться к параметрам", callback_data="back_to_params")]
        ])
        
        await call.message.edit_text(
            f"❌ Произошла ошибка при генерации поста: {str(e)}\n\n"
            f"Что делать дальше?",
            reply_markup=markup
        )


@router.callback_query(lambda c: c.data == "back_to_params")
async def back_to_basic_params(call: CallbackQuery, state: FSMContext):
    """Возврат к настройке параметров в режиме BASIC"""
    # Возвращаемся к первому шагу BASIC
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


@router.callback_query(lambda c: c.data == "back_to_post")
async def back_to_post_view(call: CallbackQuery, state: FSMContext):
    """Возврат к просмотру поста"""
    user_data = await state.get_data()
    generation_mode = user_data.get("generation_mode", "BASIC")
    generated_text = user_data.get("generated_text", "")
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Опубликовать сейчас", callback_data="post_publish_now")],
        [InlineKeyboardButton(text="🕒 Запланировать публикацию", callback_data="post_schedule")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit")],
        [InlineKeyboardButton(text="🔄 Сгенерировать другой вариант", callback_data="post_regenerate")],
        [InlineKeyboardButton(
            text="🔧 Изменить параметры" if generation_mode == "BASIC" else "📝 Изменить промпт",
            callback_data="post_change_params" if generation_mode == "BASIC" else "post_change_prompt"
        )]
    ])
    
    await call.message.edit_text(
        f"Сгенерированный пост:\n\n"
        f"{generated_text}\n\n"
        f"Выберите действие:",
        reply_markup=markup
    )
    
    # Возвращаемся к соответствующему состоянию
    if generation_mode == "BASIC":
        await state.set_state(AutoGenStates.generated_post)
    else:
        await state.set_state(AutoGenStates.pro_generated_post)
