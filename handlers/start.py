from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from handlers.group_select import choose_group

print("🔎 handlers.start imported")

router = Router()

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    # 1. сброс FSM и скрыть старую reply‑клавиатуру
    await state.clear()
    await message.answer(
        "👋 Привет! Это <b>Publicus</b> — бот для планирования и автогенерации постов.\n"
        "Сначала выбери группу или добавь новую:",
        reply_markup=ReplyKeyboardRemove()
    )
    # 2. отобразить inline‑меню выбора/добавления группы
    await choose_group(message)

# Добавляем обработчик для /start команды без фильтра текста, на случай если F.text не работает
@router.message(commands=["start"])
async def cmd_start_command(message: Message, state: FSMContext):
    await cmd_start(message, state)
