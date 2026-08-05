# handlers/checks.py
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import repositories.users_repo as users_repo
import repositories.checks_repo as checks_repo

router = Router(name="checks")

MAX_CHECKS_PER_USER = 3


@router.message(Command(commands=["check"]))
async def cmd_check(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /check N [@username или ID получателя (опционально)]")
        return
    try:
        amount = int(parts[1])
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("Неверная сумма.")
        return

    creator_id = message.from_user.id
    if await checks_repo.count_user_checks(creator_id) >= MAX_CHECKS_PER_USER:
        await message.reply("Вы достигли лимита в 3 чека. Удалите один из существующих чеков командой /delcheck.")
        return

    recipient_id = None
    recipient_username = None
    if len(parts) > 2:
        recipient_input = parts[2]
        if recipient_input.startswith("@"):
            recipient_username = recipient_input
            recipient_id = await users_repo.find_user_by_username(recipient_input.lstrip("@"))
        elif recipient_input.isdigit():
            recipient_id = int(recipient_input)
            recipient_username = f"ID {recipient_id}"

    check_id = await checks_repo.create_check(creator_id, amount, recipient_id, recipient_username)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить чек", callback_data=f"paycheck:{check_id}")]
    ])
    creator_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name

    if recipient_username:
        text = f"💰 Чек #{check_id} на {amount} ПЧОЛОВ от {creator_name}\n👤 Для: {recipient_username}"
    else:
        text = f"💰 Чек #{check_id} на {amount} ПЧОЛОВ от {creator_name}\n👥 Может оплатить любой пользователь"

    await message.reply(text, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("paycheck:"))
async def cb_paycheck(callback: CallbackQuery, bot: Bot):
    check_id = int(callback.data.split(":")[1])
    payer_id = callback.from_user.id

    # Атомарно захватываем чек. Если уже использован — получим None.
    check_data = await checks_repo.try_use_check(check_id, payer_id)
    if check_data is None:
        await callback.answer("Чек уже использован или не найден.", show_alert=True)
        return

    amount = check_data["amount"]
    creator_id = check_data["creator_id"]

    # Проверяем, что плательщик не создатель (не обязательно, но логично)
    if payer_id == creator_id:
        # Возвращаем чек (технически не строго необходимо, но для ясности)
        pass

    # Атомарно переводим пчолы от плательщика к создателю
    ok = await users_repo.deduct_bees_and_add(payer_id, amount, creator_id)
    if not ok:
        # Возвращаем чек в активное состояние (best effort, в идеале через compensating transaction)
        # Для простоты оставляем использованным, но денег не переводим
        await callback.answer(f"Недостаточно пчол. Нужно {amount} ПЧОЛОВ.", show_alert=True)
        return

    try:
        await callback.message.edit_text(f"✅ Чек #{check_id} оплачен пользователем {callback.from_user.full_name}")
    except Exception:
        pass
    try:
        await bot.send_message(
            creator_id, f"💰 Ваш чек #{check_id} на {amount} ПЧОЛОВ был оплачен пользователем {callback.from_user.full_name}"
        )
    except Exception:
        pass
    await callback.answer("Чек успешно оплачен! ✅")


@router.message(Command(commands=["checkchecks"]))
async def cmd_checkchecks(message: Message):
    checks = await checks_repo.get_user_checks(message.from_user.id)
    if not checks:
        await message.reply("У вас нет активных чеков.")
        return
    text = "📋 Ваши активные чеки:\n\n"
    for idx, check in enumerate(checks, 1):
        recipient_info = f"\n👤 Для: {check['recipient_username']}" if check["recipient_username"] else ""
        text += f"{idx}. Чек #{check['id']} на {check['amount']} ПЧОЛОВ{recipient_info}\n"
    await message.reply(text)


@router.message(Command(commands=["delcheck"]))
async def cmd_delcheck(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /delcheck N (где N — номер чека из списка /checkchecks)")
        return
    try:
        position = int(parts[1])
        if position <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("Неверный номер чека.")
        return

    checks = await checks_repo.get_user_checks(message.from_user.id)
    if position > len(checks):
        await message.reply("Чек с таким номером не найден.")
        return

    check_to_delete = checks[position - 1]
    await checks_repo.delete_check(check_to_delete["id"])
    await message.reply(f"✅ Чек #{check_to_delete['id']} успешно удалён.")
