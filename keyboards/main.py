from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Главное меню после /start
    """
    buttons = [
        [KeyboardButton(text="📅 Создать пост")],
        [KeyboardButton(text="🤖 Автогенерация постов")],
        [KeyboardButton(text="🕓 Ожидают публикации")],
        [KeyboardButton(text="📋 Очередь публикаций"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="🔙 Сменить группу")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# пример Inline-клавиатуры (если нужно для модерации и подтверждений)
def confirm_kb() -> InlineKeyboardMarkup:
    ikb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )
    return ikb
