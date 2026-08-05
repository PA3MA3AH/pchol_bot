# handlers/buybee.py
import asyncio

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import repositories.users_repo as users_repo
import repositories.buybee_repo as buybee_repo
from config import BUYBEE_CARD, BUYBEE_BANK, BUYBEE_RATE, OWNER_ID

router = Router(name="buybee")


@router.message(Command(commands=["buybee"]))
async def cmd_buybee(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /buybee N (где N — количество пчолов)")
        return
    try:
        n = int(parts[1])
        if n <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("Неверное количество.")
        return

    price = n / BUYBEE_RATE
    uid = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    req_id = await buybee_repo.create_buybee_request(uid, uname, n, price)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить перевод", callback_data=f"buybee_confirm:{req_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"buybee_cancel:{req_id}")],
    ])

    text = (
        f"Переведите сумму <b>{price:.2f} руб</b> по номеру карты:\n"
        f"<code>{BUYBEE_CARD}</code>\n"
        f"Банк: {BUYBEE_BANK}\n\n"
        f"В комментарий укажите ваш актуальный {uname}.\n\n"
        f"За ошибки (неверный комментарий, не точная сумма, не тот банк) ответственность на вас — средства не возвращаются.\n\n"
        f"Срок действия: 10 минут."
    )
    msg = await message.reply(text, reply_markup=kb)

    async def expire():
        await asyncio.sleep(600)
        row = await buybee_repo.get_buybee_request(req_id)
        if row and row["status"] == "pending":
            await buybee_repo.update_buybee_status(req_id, "expired")
            try:
                await msg.edit_text("⏰ Истёк срок действия перевода, повторите попытку.")
            except Exception:
                pass

    asyncio.create_task(expire())


@router.callback_query(lambda c: c.data and c.data.startswith("buybee_confirm:"))
async def cb_buybee_confirm(call: CallbackQuery, bot: Bot):
    req_id = int(call.data.split(":")[1])
    row = await buybee_repo.get_buybee_request(req_id)
    if not row or row["status"] != "pending":
        await call.answer("Заявка недействительна", show_alert=True)
        return
    if call.from_user.id != row["user_id"]:
        await call.answer("Вы не можете подтвердить чужую заявку.", show_alert=True)
        return
    await buybee_repo.update_buybee_status(req_id, "confirmed")
    try:
        await call.message.edit_text("✅ Вы подтвердили перевод, ожидайте зачисления (до 10 минут).")
    except Exception:
        pass

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Зачислить", callback_data=f"admin_add:{req_id}")],
        [InlineKeyboardButton(text="❌ Отказать", callback_data=f"admin_deny:{req_id}")],
    ])
    try:
        await bot.send_message(
            OWNER_ID,
            f"📥 Пользователь {row['username']} подтвердил перевод {float(row['price_rub']):.2f} руб "
            f"за {row['amount']} 🐝.\nЗачислить?",
            reply_markup=kb,
        )
    except Exception:
        pass


@router.callback_query(lambda c: c.data and c.data.startswith("buybee_cancel:"))
async def cb_buybee_cancel(call: CallbackQuery):
    req_id = int(call.data.split(":")[1])
    row = await buybee_repo.get_buybee_request(req_id)
    if not row or row["status"] != "pending":
        await call.answer("Заявка недействительна", show_alert=True)
        return
    await buybee_repo.update_buybee_status(req_id, "cancelled")
    try:
        await call.message.edit_text("❌ Вы отменили перевод.")
    except Exception:
        pass


@router.callback_query(lambda c: c.data and c.data.startswith("admin_add:"))
async def cb_admin_add(call: CallbackQuery, bot: Bot):
    if call.from_user.id != OWNER_ID:
        return
    req_id = int(call.data.split(":")[1])
    row = await buybee_repo.get_buybee_request(req_id)
    if not row or row["status"] != "confirmed":
        await call.answer("Заявка недействительна", show_alert=True)
        return
    await users_repo.add_bees_to_user(row["user_id"], row["amount"])
    await buybee_repo.update_buybee_status(req_id, "done")
    try:
        await call.message.edit_text(f"✅ Средства зачислены пользователю {row['username']} ({row['amount']} 🐝).")
    except Exception:
        pass
    try:
        await bot.send_message(row["user_id"], f"✅ Ваш перевод был засчитан, зачислено {row['amount']} 🐝.")
    except Exception:
        pass


@router.callback_query(lambda c: c.data and c.data.startswith("admin_deny:"))
async def cb_admin_deny(call: CallbackQuery, bot: Bot):
    if call.from_user.id != OWNER_ID:
        return
    req_id = int(call.data.split(":")[1])
    row = await buybee_repo.get_buybee_request(req_id)
    if not row or row["status"] != "confirmed":
        await call.answer("Заявка недействительна", show_alert=True)
        return
    await buybee_repo.update_buybee_status(req_id, "denied")
    try:
        await call.message.edit_text(f"❌ Перевод пользователя {row['username']} не был засчитан.")
    except Exception:
        pass
    try:
        await bot.send_message(row["user_id"], "❌ Ваш перевод не был засчитан, средства не начислены.")
    except Exception:
        pass
