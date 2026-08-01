# handlers/duels.py
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import repositories.users_repo as users_repo
import repositories.cards_repo as cards_repo
import repositories.game_repo as game_repo
from config import RAID_STEAL_PERCENT, RAID_STEAL_MIN, RAID_STEAL_MAX
from services.raid_logic import build_team_stats, simulate_battle

router = Router(name="duels")


def _parse_5_ids(text: str):
    return [int(x) for x in text.split(",") if x.strip().isdigit()]


@router.message(Command(commands=["beedefend"]))
async def cmd_beedefend(message: Message):
    uid = message.from_user.id
    if await users_repo.is_new_player(uid):
        await message.reply("🚫 Новички (менее 10 000 пчол и без 2 авто-ферм) не могут участвовать в дуэлях.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚙️ Использование: /beedefend id1,id2,id3,id4,id5")
        return

    ids = _parse_5_ids(parts[1])
    if len(ids) != 5:
        await message.reply("⚠️ Нужно указать ровно 5 ID карт.")
        return

    if not await cards_repo.owns_cards(uid, ids):
        await message.reply("🚫 Некоторые карты не принадлежат вам.")
        return

    await cards_repo.save_defense_deck(uid, ids)
    await message.reply("🛡️ Защитная колода сохранена.")


@router.message(Command(commands=["beeattack"]))
async def cmd_beeattack(message: Message, bot: Bot):
    uid = message.from_user.id
    if await users_repo.is_new_player(uid):
        await message.reply("🚫 Новички не могут участвовать в рейдах и дуэлях.")
        return

    # ---------- ветка 1: без reply — просто сохранить атакующую колоду ----------
    # Кулдаун тут НЕ тратится: выставление колоды — это не атака.
    if not message.reply_to_message:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("⚙️ Использование: /beeattack id1,id2,id3,id4,id5 (или reply на сообщение соперника для атаки)")
            return

        ids = _parse_5_ids(parts[1])
        if len(ids) != 5:
            await message.reply("⚠️ Нужно указать ровно 5 ID карт.")
            return

        if not await cards_repo.owns_cards(uid, ids):
            await message.reply("🚫 Некоторые карты не принадлежат вам.")
            return

        await cards_repo.save_attack_deck(uid, ids)
        await message.reply("⚔️ Атакующая колода сохранена. Чтобы атаковать — ответьте /beeattack на сообщение соперника.")
        return

    # ---------- ветка 2: reply на сообщение — реальная атака ----------
    target = message.reply_to_message.from_user
    if not target or target.is_bot:
        await message.reply("🚫 Нельзя атаковать бота.")
        return
    if target.id == uid:
        await message.reply("🚫 Нельзя атаковать самого себя.")
        return
    if await users_repo.is_new_player(target.id):
        await message.reply("🚫 Соперник — новичок, рейды на новичков запрещены.")
        return

    attacker_ids = await cards_repo.get_attack_deck(uid)
    if not attacker_ids:
        await message.reply("⚠️ У вас не выставлена атакующая колода. Сначала: /beeattack id1,id2,id3,id4,id5")
        return

    defender_ids = await cards_repo.get_defense_deck(target.id)
    if not defender_ids:
        await message.reply(f"🛡️ У {target.full_name} не выставлена защитная колода — атаковать нечего.")
        return

    # кулдаун тратится только теперь, когда бой реально состоится
    if not await game_repo.check_and_update_raid_cooldown(uid):
        await message.reply("⏳ Вы недавно уже рейдили! Попробуйте снова через пару минут.")
        return

    attacker_rows = await cards_repo.get_cards_full(attacker_ids)
    defender_rows = await cards_repo.get_cards_full(defender_ids)
    if len(attacker_rows) != 5 or len(defender_rows) != 5:
        await message.reply("⚠️ Одна из колод повреждена (карты были проданы/скрещены после выставления). Переустановите колоду.")
        return

    attacker_team = build_team_stats(attacker_rows)
    defender_team = build_team_stats(defender_rows)
    result = simulate_battle(attacker_team, defender_team)

    header = (
        f"⚔️ Рейд: {message.from_user.full_name} атакует {target.full_name}!\n\n"
        f"Атака: {', '.join(attacker_team.card_names)}\n"
        f"Защита: {', '.join(defender_team.card_names)}\n\n"
    )
    battle_log = "\n".join(result.rounds_log[-6:])  # не спамим — последние 6 раундов достаточно

    if result.winner == "draw":
        footer = "\n\n🤝 Ничья! Обе команды выстояли."
        await message.reply(header + battle_log + footer)
        return

    winner_is_attacker = result.winner == "attacker"
    winner_id = uid if winner_is_attacker else target.id
    loser_id = target.id if winner_is_attacker else uid
    winner_name = message.from_user.full_name if winner_is_attacker else target.full_name
    loser_name = target.full_name if winner_is_attacker else message.from_user.full_name

    loser_wallet = await users_repo.get_user_wallet(loser_id)
    steal = int(loser_wallet["bees"] * RAID_STEAL_PERCENT)
    steal = max(RAID_STEAL_MIN, min(RAID_STEAL_MAX, steal))
    steal = min(steal, loser_wallet["bees"])  # не уводим в минус

    if steal > 0:
        await users_repo.deduct_bees(loser_id, steal)
        await users_repo.add_bees_to_user(winner_id, steal)

    await game_repo.log_transaction(loser_id, winner_id, "BATTLE_REWARD", None, steal, "raid win")

    footer = f"\n\n🏆 Победитель: {winner_name}! Забрано {steal} 🐝 у {loser_name}."
    await message.reply(header + battle_log + footer)

    try:
        await bot.send_message(loser_id, f"⚔️ Вас атаковал {winner_name} и забрал {steal} 🐝 в бою.")
    except Exception:
        pass
