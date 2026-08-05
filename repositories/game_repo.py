# repositories/game_repo.py
from datetime import datetime, timezone

from db.pool import db
from config import RAID_COOLDOWN_SECONDS


# ---------- мини-игра "пчололов" ----------

async def start_game(user_id: int, bet: int, field_json: str):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE pchol_game SET active=FALSE WHERE user_id=$1", user_id)
        await conn.execute(
            "INSERT INTO pchol_game(user_id, bet, field) VALUES($1,$2,$3)",
            user_id, bet, field_json,
        )


async def get_active_game(user_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM pchol_game WHERE user_id=$1 AND active=TRUE", user_id
        )


async def update_game_stage(game_id: int, stage: int):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE pchol_game SET stage=$1 WHERE id=$2", stage, game_id)


async def finish_game(game_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE pchol_game SET active=FALSE WHERE id=$1", game_id)


# ---------- кулдаун рейдов ----------

async def check_and_update_raid_cooldown(user_id: int) -> bool:
    """True — атаковать можно; False — ещё на кулдауне."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_attack FROM raid_cooldown WHERE user_id=$1", user_id)
        now = datetime.now(timezone.utc)
        if row:
            last = row["last_attack"]
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            delta = (now - last).total_seconds()
            if delta < RAID_COOLDOWN_SECONDS:
                return False
            await conn.execute(
                "UPDATE raid_cooldown SET last_attack=$1 WHERE user_id=$2", now, user_id
            )
        else:
            await conn.execute(
                "INSERT INTO raid_cooldown (user_id, last_attack) VALUES ($1, $2)", user_id, now
            )
        return True


# ---------- транзакции (аудит-лог) ----------

async def log_transaction(user_from, user_to, tx_type: str, nft_id, amount, details: str = ""):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO transactions_log(user_from, user_to, type, nft_id, amount, details)
               VALUES($1,$2,$3,$4,$5,$6)""",
            user_from, user_to, tx_type, nft_id, amount, details,
        )
