# handlers/group_settings.py

from aiogram import Router, F
from aiogram.types import Message, ChatMember
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import Group

router = Router()

@router.message(F.text == "⚙️ Настройки групп")
async def group_settings_menu(message: Message):
    await message.answer(
        "Чтобы добавить группу или канал, перешлите боту любое сообщение из неё, "
        "где вы и бот являетесь администраторами."
    )

@router.message(F.forward_from_chat)
async def add_group(message: Message):
    forwarded = message.forward_from_chat
    chat_id   = forwarded.id
    title     = forwarded.title or forwarded.username or "<без названия>"

    # 1) проверяем права бота
    try:
        bot_member: ChatMember = await message.bot.get_chat_member(chat_id, message.bot.id)
    except TelegramAPIError:
        return await message.answer("❌ Я не состою в этом чате. Добавьте меня админом и повторите.")
    if bot_member.status not in ("administrator", "creator"):
        return await message.answer("❌ У меня нет прав администратора в этом чате.")

    # 2) проверяем права пользователя
    try:
        user_member: ChatMember = await message.bot.get_chat_member(chat_id, message.from_user.id)
    except TelegramAPIError:
        return await message.answer("❌ Вы не участник этого чата.")
    if user_member.status not in ("administrator", "creator"):
        return await message.answer("❌ У вас нет прав администратора в этом чате.")

    # 3) сохраняем в БД, если новая
    async with SessionLocal() as session:
        q = select(Group).where(Group.chat_id == chat_id)
        exists = (await session.execute(q)).scalar_one_or_none()
        if exists:
            return await message.answer("✅ Эта группа уже добавлена.")
        session.add(Group(chat_id=chat_id, title=title, added_by=message.from_user.id))
        await session.commit()

    # 4) подтверждаем и советуем /start
    await message.answer(
        f"✅ Группа «{title}» успешно добавлена!\n"
        "Теперь выполните /start и выберите её из списка."
    )
