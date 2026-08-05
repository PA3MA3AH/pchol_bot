# handlers/nft.py
import json

import html as _html

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import repositories.users_repo as users_repo
import repositories.cards_repo as cards_repo
import repositories.nft_repo as nft_repo
import repositories.game_repo as game_repo
from constants import generate_nft_pattern
from db.pool import db


def _he(s: str) -> str:
    """HTML-escape для безопасной вставки в Telegram HTML."""
    return _html.escape(str(s))

router = Router(name="nft")


def parse_ids_list(text: str):
    parts = [p.strip() for p in text.replace(",", " ").split() if p.strip()]
    ids = []
    for p in parts:
        try:
            ids.append(int(p))
        except ValueError:
            pass
    return ids


@router.message(Command(commands=["breed_nft"]))
async def cmd_breed_nft(message: Message):
    uid = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Использование: /breed_nft id1,id2,id3")
        return
    ids = parse_ids_list(parts[1])
    if len(ids) != 3:
        await message.reply("Нужно указать ровно 3 ID карточек.")
        return

    rows = await cards_repo.get_cards_by_instance_ids(ids)
    if len(rows) != 3 or any(r["user_id"] != uid for r in rows):
        await message.reply("Некоторые карточки не найдены в вашей коллекции.")
        return
    if any(r["level"] < 5 for r in rows):
        await message.reply("Все три карточки должны быть 5 уровня.")
        return

    if await nft_repo.count_user_nfts(uid) >= nft_repo.MAX_NFT_PER_USER:
        await message.reply("У вас уже максимум 5 NFT.")
        return

    total_nfts = await nft_repo.count_total_nfts()
    if total_nfts >= nft_repo.MAX_NFT_TOTAL:
        await message.reply("Все 150 NFT уже созданы.")
        return

    next_id = total_nfts + 1
    name = f"NFT-Пчела #{next_id}"
    md = {"origin_cards": ids, "creator": uid, "serial": next_id}
    nft_id = await nft_repo.create_nft(uid, name, md)
    await cards_repo.delete_cards(ids)

    await message.reply(f"✨ Поздравляю! Создан NFT #{nft_id}: {name}.")


@router.message(Command(commands=["giftnft"]))
async def cmd_giftnft(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Использование: /giftnft @username <nft_id> или /giftnft <user_id> <nft_id>")
        return
    target = parts[1]
    try:
        nft_id = int(parts[2])
    except ValueError:
        await message.reply("Неверный NFT ID.")
        return
    sender = message.from_user.id

    if target.startswith("@"):
        try:
            chat = await bot.get_chat(target)
            rid = chat.id
        except Exception:
            await message.reply("Не удалось найти пользователя по username.")
            return
    elif target.isdigit():
        rid = int(target)
    else:
        await message.reply("Укажите @username или numeric ID.")
        return

    nft = await nft_repo.get_nft(nft_id)
    if not nft or nft["owner"] != sender:
        await message.reply("NFT не найден или не принадлежит вам.")
        return
    if await nft_repo.count_user_nfts(rid) >= nft_repo.MAX_NFT_PER_USER:
        await message.reply("У получателя уже максимум 5 NFT.")
        return

    await nft_repo.transfer_nft(nft_id, sender, rid)
    await message.reply("✅ NFT успешно передан.")
    try:
        await bot.send_message(
            rid, f"🎁 Вам подарили NFT #{nft_id} от @{message.from_user.username or message.from_user.full_name}"
        )
    except Exception:
        pass


@router.message(Command(commands=["nft_sell"]))
async def cmd_nft_sell(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("⚠️ Использование: /nft_sell <nft_id> <price_bees>")
        return
    try:
        nft_id = int(parts[1])
        price = int(parts[2])
    except ValueError:
        await message.reply("⚠️ NFT ID и цена должны быть числами.")
        return
    if price <= 0:
        await message.reply("⚠️ Цена должна быть больше нуля.")
        return

    seller = message.from_user.id
    nft = await nft_repo.get_nft(nft_id)
    if not nft:
        await message.reply("🚫 NFT с таким ID не найден.")
        return
    if nft["owner"] != seller:
        await message.reply("🚫 Этот NFT вам не принадлежит.")
        return
    if await nft_repo.is_listed(nft_id):
        await message.reply("⚠️ Этот NFT уже выставлен на продажу.")
        return

    await nft_repo.list_nft(nft_id, seller, price)
    await message.reply(f"✅ NFT <b>{nft['name']}</b> (#{nft_id}) выставлен на продажу за {price} пчол.", parse_mode="HTML")


@router.message(Command(commands=["nft_list"]))
async def cmd_nft_list(message: Message):
    rows = await nft_repo.get_marketplace_listings()
    if not rows:
        await message.reply("📭 На бирже нет активных лотов NFT.")
        return
    text = "<b>🛒 Лоты NFT на бирже:</b>\n\n"
    for r in rows:
        text += (f"Lot {r['lot_id']}: NFT#{r['nft_id']} — {r['name']}\n"
                 f"Цена: {r['price_bees']} пчол — Продавец: <code>{r['seller']}</code>\n\n")
    await message.reply(text, parse_mode="HTML")


@router.message(Command(commands=["stopsell"]))
async def cmd_stopsell(message: Message):
    uid = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /stopsell #N")
        return
    try:
        nft_id = int(parts[1].lstrip("#"))
    except ValueError:
        await message.reply("Неверный формат NFT. Используйте #номер.")
        return

    listing = await nft_repo.get_listing_by_nft(nft_id)
    if not listing:
        await message.reply(f"NFT #{nft_id} не выставлен на продажу.")
        return
    if listing["seller"] != uid:
        await message.reply(f"Невозможно снять с продажи NFT #{nft_id} другого пользователя.")
        return

    await nft_repo.unlist_nft(nft_id)
    await message.reply(f"NFT #{nft_id} успешно снят с продажи.")


@router.message(Command(commands=["nft_buy"]))
async def cmd_nft_buy(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ Использование: /nft_buy <lot_id>")
        return
    try:
        lot_id = int(parts[1])
    except ValueError:
        await message.reply("⚠️ LOT_ID должен быть числом.")
        return

    buyer = message.from_user.id
    result = await nft_repo.buy_lot_atomic(lot_id, buyer)

    errors = {
        "not_found": "🚫 Лот не найден.",
        "own_lot": "⚠️ Вы не можете купить свой лот.",
        "insufficient_funds": "🚫 Недостаточно пчол для покупки.",
    }
    if result.get("error"):
        await message.reply(errors.get(result["error"], "Ошибка покупки."))
        return

    nft_id = result["nft_id"]
    seller = result["seller"]
    price = result["price"]

    await message.reply("✅ Покупка выполнена. NFT теперь у вас.")
    try:
        await bot.send_message(
            seller,
            f"💰 Ваш NFT #{nft_id} был куплен пользователем <code>{buyer}</code> за {price} пчол!",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.reply(
        f"📜 Чек сделки:\nNFT: #{nft_id}\nПродавец: {seller}\nЦена: {price} пчол\nСтатус: ✅ Успешно",
        parse_mode="HTML",
    )
    await game_repo.log_transaction(seller, buyer, "NFT_SALE", nft_id, price, f"NFT продан за {price} пчол")


@router.message(Command(commands=["bee_pattern"]))
async def cmd_bee_pattern(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /bee_pattern #N")
        return
    try:
        nft_id = int(parts[1].lstrip("#"))
    except ValueError:
        await message.reply("Неверный формат NFT. Используйте #номер.")
        return

    nft = await nft_repo.get_nft(nft_id)
    if not nft:
        await message.reply(f"NFT #{nft_id} не найден.")
        return
    listing = await nft_repo.get_listing_by_nft(nft_id)

    async with db.pool.acquire() as conn:
        owner_row = await conn.fetchrow("SELECT username FROM users WHERE user_id=$1", nft["owner"])
    owner_name = owner_row["username"] if owner_row and owner_row["username"] else f"User {nft['owner']}"

    try:
        metadata = json.loads(nft["metadata"]) if nft["metadata"] else {}
    except Exception:
        metadata = {}

    color = metadata.get("color", "Не задано")
    symbol = metadata.get("symbol", "Не задано")
    bee_type = metadata.get("bee", "Не задано")

    await message.reply("🐝")
    await message.reply(
        f"Паттерн NFT-пчолы #{nft_id}:\n"
        f"Владелец: {owner_name}\n"
        f"Цвет фона: {color}\n"
        f"Символ фона: {symbol}\n"
        f"Модель пчолы: {bee_type}\n"
        f"В продаже: {'✅' if listing else '❌'}"
        + (f"\nЦена: {listing['price_bees']} пчол" if listing else "")
    )


@router.message(Command(commands=["upgrade_nft"]))
async def cmd_upgrade_nft(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /upgrade_nft #N")
        return
    try:
        nft_id = int(parts[1].lstrip("#"))
    except ValueError:
        await message.reply("Неверный формат NFT. Используйте #номер.")
        return

    uid = message.from_user.id
    required_honey = 250

    nft = await nft_repo.get_nft(nft_id)
    if not nft:
        await message.reply(f"NFT #{nft_id} не найден.")
        return
    if nft["owner"] != uid:
        await message.reply("Невозможно изменить паттерн NFT, который принадлежит другому пользователю.")
        return

    async with db.pool.acquire() as conn:
        user = await conn.fetchrow("SELECT honey, bees, username FROM users WHERE user_id=$1", uid)
    if not user:
        await message.reply("Пользователь не найден в базе.")
        return

    total_honey_equiv = user["honey"] + user["bees"] / 1000
    if total_honey_equiv < required_honey:
        await message.reply(f"Недостаточно мёда для покупки паттерна. Нужно {required_honey} мёда.")
        return

    new_honey = user["honey"] - required_honey
    new_bees = user["bees"]
    if new_honey < 0:
        deficit = -new_honey
        new_bees -= int(deficit * 1000)
        new_honey = 0

    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET honey=$1, bees=$2 WHERE user_id=$3", new_honey, new_bees, uid)

    try:
        metadata = json.loads(nft["metadata"]) if nft["metadata"] else {}
    except Exception:
        metadata = {}

    if "creator" not in metadata:
        metadata["creator"] = user["username"] or f"User {uid}"
    metadata["owner"] = user["username"] or f"User {uid}"
    metadata.update(generate_nft_pattern(nft_id))

    await nft_repo.update_nft_metadata(nft_id, metadata)

    await message.reply(
        f"✅ Паттерн NFT #{nft_id} успешно приобретён!\n"
        f"Создатель: {metadata['creator']}\n"
        f"Владелец: {metadata['owner']}\n"
        f"Цвет фона: {metadata['color']}\n"
        f"Символ фона: {metadata['symbol']}\n"
        f"Модель пчолы: {metadata['bee']}\n"
        f"Списано: {required_honey} мёда"
    )


@router.message(Command(commands=["myachivepchol"]))
async def cmd_myachive(message: Message):
    uid = message.from_user.id
    rows = await nft_repo.get_user_achievements(uid)
    if not rows:
        await message.reply("У вас нет достижений.")
        return
    text = "🏆 Ваши достижения:\n"
    for r in rows:
        text += f"- {r['achv_key']} ({r['achieved_at'].strftime('%Y-%m-%d')})\n"
    await message.reply(text)


async def grant_achievement(bot: Bot, user_id: int, key: str):
    granted = await nft_repo.grant_achievement_if_new(user_id, key)
    if granted:
        try:
            await bot.send_message(user_id, f"🏆 Достигнуто достижение: {key}")
        except Exception:
            pass
