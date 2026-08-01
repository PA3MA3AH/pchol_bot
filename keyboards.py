# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def confirm_cancel_kb(confirm_cb: str, cancel_cb: str,
                       confirm_text: str = "✅", cancel_text: str = "❌") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_cb),
            InlineKeyboardButton(text=cancel_text, callback_data=cancel_cb),
        ]
    ])
