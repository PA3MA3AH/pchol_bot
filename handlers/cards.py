# handlers/cards.py
import random

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import repositories.users_repo as users_repo
import repositories.cards_repo as cards_repo
from config import PACK_PRICE, DUPLICATE_CONVERT_BEES
from constants import UPGRADE_COSTS

router = Router(name="cards")


@router.message(Command(commands=["beepack"]))
async def cmd_beepack(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /beepack N (N — количество паков)")
        return
    try:
        n = int(parts[1])
        if n <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("Неверное число паков.")
        return

    uid = message.from_user.id
    total_cost = PACK_PRICE * n
    ok = await users_repo.deduct_bees(uid, total_cost)
    if not ok:
        await message.reply(f"Недостаточно пчол. Нужно {total_cost} пчол.")
        return

    all_card_ids = await cards_repo.get_all_card_ids()
    if not all_card_ids:
        await users_repo.add_bees_to_user(uid, total_cost)  # возвращаем деньги, каталог пуст
        await message.reply("Каталог карт пуст.")
        return

    awarded = []
    refunded_bees = 0

    for _ in range(n):
        how_many = random.choice([1, 2])
        selected = random.sample(all_card_ids, k=min(how_many, len(all_card_ids)))
        for cid in selected:
            existing = await cards_repo.user_has_card(uid, cid)
            if existing:
                refunded_bees += DUPLICATE_CONVERT_BEES
            else:
                inst = await cards_repo.add_user_card(uid, cid, level=1)
                awarded.append((inst, cid))

    if refunded_bees > 0:
        await users_repo.add_bees_to_user(uid, refunded_bees)

    text = f"🎁 Вы открыли {n} паков.\n\n"
    if awarded:
        text += "Вы получили карточки:\n"
        card_name_map = await cards_repo.get_card_names([cid for _, cid in awarded])
        for inst, cid in awarded:
            name = card_name_map.get(cid, f"Card {cid}")
            text += f"• {name} (id={inst})\n"
    if refunded_bees > 0:
        text += f"\n🔁 Дубликаты конвертированы в {refunded_bees} пчол."

    await bot.send_message(uid, text)
    await message.reply("Пак(и) куплены и отправлены вам в ЛС.")


@router.message(Command(commands=["beecards"]))
async def cmd_beecards(message: Message, bot: Bot):
    uid = message.from_user.id
    rows = await cards_repo.get_user_cards(uid)
    if not rows:
        await message.reply("У вас нет карточек.")
        return

    text = "🎴 Ваша коллекция карточек:\n\n"
    for r in rows:
        text += f"ID {r['instance_id']}: {r['name']} — {r['class']} — {r['level']}⭐\n"
    await bot.send_message(uid, text)
    await message.reply("Коллекция отправлена в ЛС.")


@router.message(Command(commands=["upgradecard"]))
async def cmd_upgradecard(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /upgradecard <instance_id>")
        return
    try:
        inst = int(parts[1])
    except ValueError:
        await message.reply("Неверный ID карточки.")
        return

    uid = message.from_user.id
    row = await cards_repo.get_card_instance(inst)
    if not row or row["user_id"] != uid:
        await message.reply("Карточка не найдена в вашей коллекции.")
        return

    lvl = row["level"]
    if lvl >= 5:
        await message.reply("Карточка уже максимального уровня.")
        return

    next_lvl = lvl + 1
    cost = UPGRADE_COSTS[next_lvl]
    wallet = await users_repo.get_user_wallet(uid)
    if wallet["honey"] + 1e-9 < cost:
        await message.reply(f"Недостаточно мёда. Нужно {cost} мёда. У вас {wallet['honey']:.3f}.")
        return

    await users_repo.deduct_honey(uid, cost)
    await cards_repo.set_card_level(inst, next_lvl)
    await message.reply(f"✅ Карточка {inst} улучшена до {next_lvl} уровня. Потрачено {cost} мёда.")
