# handlers/wallet.py
import html

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from constants import WALLET_TRIGGERS
from db.pool import db
import repositories.users_repo as users_repo

router = Router(name="wallet")


def _h(s: str) -> str:
    return html.escape(str(s))


@router.message(Command(commands=["pchol"]))
async def cmd_pchol(message: Message):
    total = await users_repo.get_total(message.chat.id)
    await message.reply(f"В этом чате улей на {total} ПЧОЛОВ 🐝")


@router.message(Command(commands=["top"]))
async def cmd_topbees(message: Message, bot: Bot):
    rows = await users_repo.get_top(message.chat.id)
    if not rows:
        await message.reply("Пока никто не отправил 🐝.")
        return
    text = "🏆 Топ 10 Сильнейших ПЧОЛО-отправителей:\n"
    for row in rows:
        try:
            user = await bot.get_chat(row["user_id"])
            name = user.full_name
        except Exception:
            name = f"ID {row['user_id']}"
        text += f"{row['position']}. {name} — {row['total_bees']} 🐝\n"
    await message.reply(text)


@router.message(lambda m: m.text and m.text.strip() in WALLET_TRIGGERS)
async def cmd_wallet(message: Message):
    uid = message.from_user.id
    w = await users_repo.get_user_wallet(uid)

    async with db.pool.acquire() as conn:
        nfts = await conn.fetch(
            "SELECT nft_id, metadata FROM nfts WHERE owner=$1 ORDER BY nft_id", uid
        )

    if nfts:
        nft_text = ", ".join(f"🐝 #{r['nft_id']}" for r in nfts)
    else:
        nft_text = "Нет NFT-пчёл"

    text = (
        f"💼 Кошелёк {_h(message.from_user.full_name)}:\n"
        f"Мёд: {w['honey']:.3f}\n"
        f"Пчолы: {w['bees']}\n"
        f"Авто-фермы: {w['farms']} (каждая даёт ~2 пчол/мин)\n"
        f"Бусты: {w['boosts']} (даёт +0.5 пчол/мин к каждой ферме)\n"
        f"NFT-пчолы: {nft_text}"
    )
    await message.reply(text)
