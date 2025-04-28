from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from database.db import SessionLocal
from database.models import GeneratedSeries

router = Router()

class AutoGenStates(StatesGroup):
    prompt = State()
    repeat = State()
    gen_time = State()
    post_limit = State()
    moderation = State()
    confirm = State()

@router.message(F.text == "🤖 Автогенерация постов")
async def start_auto_gen(message: Message, state: FSMContext):
    await message.answer("📄 Введите шаблон для генерации:")
    await state.set_state(AutoGenStates.prompt)

@router.message(AutoGenStates.prompt)
async def set_prompt(message: Message, state: FSMContext):
    await state.update_data(prompt=message.text)
    await message.answer("🔁 Повторять каждый день?\nДа / Нет")
    await state.set_state(AutoGenStates.repeat)

@router.message(AutoGenStates.repeat)
async def set_repeat(message: Message, state: FSMContext):
    repeat = message.text.lower() == "да"
    await state.update_data(repeat=repeat)
    await message.answer("🕒 Укажите время генерации в формате ЧЧ:ММ (например, 12:00)")
    await state.set_state(AutoGenStates.gen_time)

@router.message(AutoGenStates.gen_time)
async def set_time(message: Message, state: FSMContext):
    try:
        gen_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(gen_time=gen_time.strftime("%H:%M"))
        await message.answer("🔢 Сколько постов сгенерировать максимум? (по умолчанию 10)")
        await state.set_state(AutoGenStates.post_limit)
    except ValueError:
        await message.answer("⛔ Неверный формат времени. Попробуйте снова (например, 12:00).")

@router.message(AutoGenStates.post_limit)
async def set_limit(message: Message, state: FSMContext):
    try:
        limit = int(message.text)
        await state.update_data(post_limit=limit)
    except ValueError:
        await state.update_data(post_limit=10)
    await message.answer("👁 Включить премодерацию? Да / Нет")
    await state.set_state(AutoGenStates.moderation)

@router.message(AutoGenStates.moderation)
async def set_moderation(message: Message, state: FSMContext):
    mod = message.text.lower() == "да"
    await state.update_data(moderation=mod)

    data = await state.get_data()
    summary = (
        f"📄 Шаблон: {data['prompt']}\n"
        f"🔁 Повтор: {'Да' if data['repeat'] else 'Нет'}\n"
        f"🕒 Время генерации: {data['gen_time']}\n"
        f"🔢 Лимит: {data['post_limit']}\n"
        f"👁 Премодерация: {'Да' if data['moderation'] else 'Нет'}"
    )
    await message.answer(
        f"✅ Проверьте параметры:\n\n{summary}\n\nЗапускаем?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить", callback_data="start_gen")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_gen")]
        ])
    )
    await state.set_state(AutoGenStates.confirm)

@router.callback_query(F.data == "start_gen")
async def confirm_gen(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with SessionLocal() as session:
        series = GeneratedSeries(
            chat_id=call.message.chat.id,
            prompt=data['prompt'],
            repeat=data['repeat'],
            time=data['gen_time'],
            post_limit=data['post_limit'],
            posts_generated=0,
            moderation=data['moderation']
        )
        session.add(series)
        await session.commit()
    await call.message.edit_text("🚀 Серия автогенерации создана и запущена!")
    await state.clear()

@router.callback_query(F.data == "cancel_gen")
async def cancel_gen(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ Автогенерация отменена.")
    await state.clear()