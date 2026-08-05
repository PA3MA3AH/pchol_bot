# handlers/farms_boosts.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import repositories.users_repo as users_repo
from config import BEEBOOST_PRICE
from services.economy import beefarm_total_cost

router = Router(name="farms_boosts")


MAX_FARMS = 1000000  # ~1 млн ферм максимум
MAX_BOOSTS = 1000000

@router.message(Command(commands=["beefarm"]))
async def cmd_beefarm(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /beefarm N")
        return
    try:
        n = int(parts[1])
        if n <= 0 or n > MAX_FARMS:
            raise ValueError()
    except ValueError:
        await message.reply(f"Неверное число. Укажите от 1 до {MAX_FARMS}.")
        return


    uid = message.from_user.id
    wallet = await users_repo.get_user_wallet(uid)
    total_cost = beefarm_total_cost(wallet["farms"], n)

    ok = await users_repo.deduct_bees(uid, total_cost)
    if not ok:
        await message.reply(f"Недостаточно пчол. Нужно {total_cost} пчол.")
        return

    await users_repo.add_farms(uid, n)
    await message.reply(f"Вы успешно купили {n} авто-ферм, списано {total_cost} пчол.")


@router.message(Command(commands=["beeboost"]))
async def cmd_beeboost(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /beeboost N")
        return
    try:
        n = int(parts[1])
        if n <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("Неверное число.")
        return

    uid = message.from_user.id
    bees_cost = n * BEEBOOST_PRICE
    ok = await users_repo.deduct_bees(uid, bees_cost)
    if not ok:
        await message.reply(f"Недостаточно пчол. Нужно {bees_cost} пчол.")
        return
    await users_repo.add_boosts(uid, n)
    await message.reply(f"Вы успешно купили {n} бустов, списано {bees_cost} пчол.")
