from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.db import AsyncSessionLocal
from database.models import Group
from keyboards.main import main_menu_kb

print("🔎 handlers.group_select imported")

router = Router()

@router.message(F.text == "🔙 Сменить группу")
async def choose_group(message: Message):
    # получить все группы, которые добавил этот пользователь
    async with AsyncSessionLocal() as session:
        groups = (await session.execute(
            select(Group).where(Group.added_by == message.from_user.id)
        )).scalars().all()

    # собрать inline‑кнопки: сначала группы, затем всегда настройка
    buttons = [
        [InlineKeyboardButton(text=g.title, callback_data=f"sel_{g.id}")]
        for g in groups
    ]
    # иконка «⚙️ Настройки групп» всегда последней
    buttons.append([InlineKeyboardButton(text="⚙️ Настройки групп", callback_data="open_group_settings")])
    ikb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if not groups:
        # нет групп — сообщение + одна кнопка
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

@router.callback_query(F.data.startswith("sel_"))
async def select_group(call: CallbackQuery, state: FSMContext):
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

@router.callback_query(F.data == "open_group_settings")
async def open_settings(call: CallbackQuery):
    # удаляем текущее сообщение
    await call.message.delete()
    # отправляем инструкцию по добавлению новой группы
    await call.bot.send_message(
        call.from_user.id,
        "Перешлите боту любое сообщение из группы/канала, чтобы добавить её."
    )
