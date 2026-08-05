# handlers/transfers.py
import re
from typing import Dict

from aiogram import Router, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
)

import repositories.users_repo as users_repo

router = Router(name="transfers")

TRANSFER_START_RE = re.compile(r"@pcholcounterbot\s+(\d+)", flags=re.IGNORECASE)
transfer_sessions: Dict[int, dict] = {}


@router.message(lambda m: m.text and TRANSFER_START_RE.search(m.text))
async def handle_transfer_start(message: Message, bot: Bot):
    m = TRANSFER_START_RE.search(message.text)
    n = int(m.group(1))
    sender_id = message.from_user.id
    wallet = await users_repo.get_user_wallet(sender_id)
    if wallet["bees"] < n:
        await message.reply("Недостаточно пчол для перевода.")
        return

    prompt_text = (
        f"🐝 Вы начали перевод {n} ПЧОЛОВ\n"
        "Зайдите в личные сообщения бота и введите @имя_пользователя или Telegram ID получателя\n"
        "Выбран пользователь: None"
    )

    try:
        sent = await message.reply(prompt_text)
        group_chat = sent.chat.id
        group_msg_id = sent.message_id
    except Exception:
        group_chat = message.chat.id
        group_msg_id = None

    transfer_sessions[sender_id] = {
        "amount": n,
        "recipient": None,
        "group_chat": group_chat,
        "group_msg_id": group_msg_id,
        "ls_msg_id": None,
    }

    try:
        pm = await bot.send_message(sender_id, "Напишите @имя_пользователя или Telegram ID (число) получателя")
        transfer_sessions[sender_id]["ls_msg_id"] = pm.message_id
    except Exception:
        try:
            await message.reply("Я не могу написать вам в ЛС — начните чат со мной и повторите перевод.")
        except Exception:
            pass


@router.message(lambda m: m.chat.type == "private" and m.text and (
    m.text.strip().startswith("@") or m.text.strip().isdigit()
))
async def handle_transfer_recipient(message: Message):
    sender_id = message.from_user.id
    session = transfer_sessions.get(sender_id)
    if not session:
        try:
            await users_repo.update_username(sender_id, message.from_user.username or None)
        except Exception:
            pass
        return

    recipient_input = message.text.strip()
    session["recipient"] = recipient_input
    amount = session["amount"]

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅", callback_data=f"transfer_confirm:{sender_id}"),
        InlineKeyboardButton(text="❌", callback_data=f"transfer_cancel:{sender_id}"),
    ]])
    await message.reply(f"Выбран получатель {recipient_input} для перевода {amount} ПЧОЛОВ, всё верно?", reply_markup=kb)


@router.callback_query(lambda c: c.data and (c.data.startswith("transfer_confirm:") or c.data.startswith("transfer_cancel:")))
async def cb_transfer(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    try:
        action, sender_id_s = callback.data.split(":", 1)
    except ValueError:
        return
    sender_id = int(sender_id_s)
    session = transfer_sessions.get(sender_id)
    if not session:
        await callback.message.edit_text("Сессия не найдена или устарела.")
        return

    recipient_input = session.get("recipient")
    amount = session.get("amount", 0)
    group_chat = session.get("group_chat")
    group_msg_id = session.get("group_msg_id")
    sender_username = callback.from_user.username or f"id{sender_id}"

    if action == "transfer_cancel":
        clicker = callback.from_user
        clicker_ok = clicker.id == sender_id
        if not clicker_ok and recipient_input:
            if recipient_input.startswith("@"):
                if (clicker.username or "").lower() == recipient_input.lstrip("@").lower():
                    clicker_ok = True
            elif recipient_input.isdigit() and clicker.id == int(recipient_input):
                clicker_ok = True
        if not clicker_ok:
            await callback.answer("Отклонить может только отправитель или получатель.", show_alert=True)
            return
        try:
            await callback.message.edit_text("Перевод отменён.")
        except Exception:
            pass
        transfer_sessions.pop(sender_id, None)
        return

    if action == "transfer_confirm":
        if callback.from_user.id != sender_id:
            await callback.answer("Подтвердить может только отправитель.", show_alert=True)
            return
        if not recipient_input:
            await callback.answer("Получатель не выбран.", show_alert=True)
            return

        ok = await users_repo.deduct_bees(sender_id, amount)
        if not ok:
            try:
                await callback.message.edit_text("У отправителя недостаточно пчол.")
            except Exception:
                pass
            transfer_sessions.pop(sender_id, None)
            return

        recipient_id = None
        if recipient_input.startswith("@"):
            recipient_id = await users_repo.find_user_by_username(recipient_input.lstrip("@"))
            if not recipient_id:
                try:
                    chat = await bot.get_chat(recipient_input)
                    recipient_id = chat.id
                except Exception:
                    pass
        elif recipient_input.isdigit():
            recipient_id = int(recipient_input)

        if not recipient_id:
            await users_repo.add_bees_to_user(sender_id, amount)
            try:
                await callback.message.edit_text(f"Пользователь {recipient_input} не найден. Перевод отменён.")
            except Exception:
                pass
            transfer_sessions.pop(sender_id, None)
            return

        await users_repo.add_bees_to_user(recipient_id, amount)
        try:
            await users_repo.log_transfer(sender_id, recipient_id, recipient_input, amount)
        except Exception:
            pass

        try:
            if group_msg_id:
                new_text = (
                    f"🐝 Вы начали перевод {amount} ПЧОЛОВ\n"
                    "Зайдите в личные сообщения бота и введите @имя_пользователя или Telegram ID получателя\n"
                    f"Выбран пользователь: {recipient_input}"
                )
                await bot.edit_message_text(chat_id=group_chat, message_id=group_msg_id, text=new_text)
            await bot.send_message(group_chat, f"Успешно переведены {amount} ПЧОЛОВ от @{sender_username} для {recipient_input}")
        except Exception:
            pass

        try:
            await callback.message.edit_text("Перевод успешно выполнен ✅")
        except Exception:
            pass

        transfer_sessions.pop(sender_id, None)
        return


@router.inline_query()
async def inline_transfer(query: InlineQuery):
    text = (query.query or "").strip()
    if not text or not re.fullmatch(r"\d+", text):
        return
    n = int(text)
    if n <= 0:
        return
    result = InlineQueryResultArticle(
        id=f"transfer_{n}_{query.from_user.id}",
        title=f"Перевести {n} ПЧОЛОВ 🐝",
        description=f"Оформить перевод {n} пчол — нажмите, затем укажите получателя в ЛС бота",
        input_message_content=InputTextMessageContent(message_text=f"@pcholcounterbot {n}"),
    )
    await query.answer(results=[result], cache_time=1, is_personal=True)
