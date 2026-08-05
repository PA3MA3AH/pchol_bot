# handlers/minigame.py
import json
import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import repositories.users_repo as users_repo
import repositories.game_repo as game_repo

router = Router(name="minigame")

MULTIPLIERS_PREVIEW = [4096, 2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2]


@router.message(Command(commands=["getpchol"]))
async def cmd_getpchol(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /getpchol N (ставка в пчолах)")
        return
    try:
        bet = int(parts[1])
        if bet <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Неверное число. Введите положительное число пчол.")
        return

    uid = message.from_user.id
    ok = await users_repo.deduct_bees(uid, bet)
    if not ok:
        await message.reply(f"Недостаточно пчол для ставки {bet}.")
        return

    field = []
    for _ in range(12):
        field.append(["🐝", "❌"] if random.choice([True, False]) else ["❌", "🐝"])
    field_json = json.dumps(field, ensure_ascii=False)

    await game_repo.start_game(uid, bet, field_json)

    text = f'Вы начали мини-игру "пчололов". Сумма ставки: {bet}\n'
    for m in MULTIPLIERS_PREVIEW:
        text += f"| ❓ | ❓ | {bet*m} пчолов ({m}х)\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="|❓| ⬅", callback_data=f"pchol:{uid}:left"),
        InlineKeyboardButton(text="➡ |❓|", callback_data=f"pchol:{uid}:right"),
    ]])
    await message.reply(text, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("pchol:"))
async def cb_pchol(callback: CallbackQuery):
    _, uid_s, side = callback.data.split(":")
    uid = int(uid_s)
    if callback.from_user.id != uid:
        await callback.answer("Это не ваша игра!", show_alert=True)
        return

    game = await game_repo.get_active_game(uid)
    if not game:
        await callback.answer("Игра не найдена или уже завершена.", show_alert=True)
        return

    field = json.loads(game["field"])
    stage = game["stage"]
    bet = game["bet"]

    cell_index = 0 if side == "left" else 1
    symbol = field[stage][cell_index]

    if symbol == "❌":
        reveal = "\n".join(f"| {r[0]} | {r[1]} |" for r in field)
        await game_repo.finish_game(game["id"])
        await callback.message.edit_text(f"❌ Ловушка! Вы проиграли!\nПоле:\n{reveal}")
        return

    stage += 1
    multiplier = 2 ** stage
    win = bet * multiplier
    await game_repo.update_game_stage(game["id"], stage)

    if stage >= len(field):
        await game_repo.finish_game(game["id"])
        await users_repo.add_bees_to_user(uid, win)
        await callback.message.edit_text(f"🏆 Поздравляем! Вы прошли все уровни и выиграли {win} пчол!")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="|❓| ⬅", callback_data=f"pchol:{uid}:left"),
            InlineKeyboardButton(text="➡ |❓|", callback_data=f"pchol:{uid}:right"),
        ],
        [InlineKeyboardButton(text=f"💰 Забрать {win} ({multiplier}х)", callback_data=f"takep:{uid}:{win}")],
    ])
    await callback.message.edit_text(
        f"🐝 Отлично! Вы нашли пчолу!\nТекущий множитель: {multiplier}х\nМожно забрать {win} пчол.",
        reply_markup=kb,
    )


@router.callback_query(lambda c: c.data and c.data.startswith("takep:"))
async def cb_take_pchol(callback: CallbackQuery):
    _, uid_s, win_s = callback.data.split(":")
    uid = int(uid_s)
    win = int(win_s)
    if callback.from_user.id != uid:
        await callback.answer("Это не ваша игра!", show_alert=True)
        return

    game = await game_repo.get_active_game(uid)
    if not game:
        await callback.answer("Игра уже завершена или не найдена.", show_alert=True)
        return

    field = json.loads(game["field"])
    reveal = "\n".join(f"| {r[0]} | {r[1]} |" for r in field)
    await game_repo.finish_game(game["id"])
    await users_repo.add_bees_to_user(uid, win)
    await callback.message.edit_text(f"🎉 Вы забрали {win} пчол! Игра окончена.\nВот поле:\n{reveal}")
