# repositories/users_repo.py
from typing import Optional, Tuple

from db.pool import db


# ---------- chats / messages / top ----------

async def ensure_chat_exists(chat_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chats(chat_id, total_bees) VALUES($1, 0) ON CONFLICT DO NOTHING",
            chat_id,
        )


async def ensure_user(user_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING", user_id
        )


async def add_message_count(chat_id: int, message_id: int, bees: int, user_id: int):
    await ensure_chat_exists(chat_id)
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO messages(chat_id, message_id, user_id, bees_count)
                VALUES($1,$2,$3,$4)
                ON CONFLICT (chat_id, message_id) DO NOTHING
                """,
                chat_id, message_id, user_id, bees,
            )
            if bees > 0:
                await conn.execute(
                    "UPDATE chats SET total_bees = total_bees + $1 WHERE chat_id=$2",
                    bees, chat_id,
                )
                await conn.execute(
                    "UPDATE users SET bees = bees + $1 WHERE user_id=$2",
                    bees, user_id,
                )
    await update_top(chat_id)


async def update_message_on_edit(chat_id: int, message_id: int, new_bees: int, user_id: int):
    await ensure_chat_exists(chat_id)
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT bees_count FROM messages WHERE chat_id=$1 AND message_id=$2",
                chat_id, message_id,
            )
            if row:
                diff = new_bees - row["bees_count"]
                if diff != 0:
                    await conn.execute(
                        "UPDATE chats SET total_bees = total_bees + $1 WHERE chat_id=$2",
                        diff, chat_id,
                    )
                    await conn.execute(
                        "UPDATE users SET bees = bees + $1 WHERE user_id=$2",
                        diff, user_id,
                    )
                await conn.execute(
                    "UPDATE messages SET bees_count=$1, user_id=$2 WHERE chat_id=$3 AND message_id=$4",
                    new_bees, user_id, chat_id, message_id,
                )
            else:
                await add_message_count(chat_id, message_id, new_bees, user_id)
    await update_top(chat_id)


async def get_total(chat_id: int) -> int:
    await ensure_chat_exists(chat_id)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT total_bees FROM chats WHERE chat_id=$1", chat_id)
        return row["total_bees"] if row else 0


async def get_user_bees_in_chat(chat_id: int, user_id: int) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT SUM(bees_count) AS s FROM messages WHERE chat_id=$1 AND user_id=$2",
            chat_id, user_id,
        )
        return row["s"] or 0


async def ensure_zero_message(chat_id: int, message_id: int, user_id: int):
    await ensure_chat_exists(chat_id)
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO messages(chat_id, message_id, user_id, bees_count)
            VALUES($1,$2,$3,0)
            ON CONFLICT DO NOTHING
            """,
            chat_id, message_id, user_id,
        )


async def update_top(chat_id: int):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, SUM(bees_count) as total_bees
            FROM messages
            WHERE chat_id=$1
            GROUP BY user_id
            ORDER BY total_bees DESC
            LIMIT 10
            """,
            chat_id,
        )
        await conn.execute("DELETE FROM top_users WHERE chat_id=$1", chat_id)
        for pos, row in enumerate(rows, start=1):
            await conn.execute(
                "INSERT INTO top_users(chat_id, user_id, position, total_bees) VALUES($1,$2,$3,$4)",
                chat_id, row["user_id"], pos, row["total_bees"],
            )


async def get_top(chat_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            "SELECT user_id, position, total_bees FROM top_users WHERE chat_id=$1 ORDER BY position ASC",
            chat_id,
        )


# ---------- frozen users ----------

async def freeze_user(user_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO frozen_users(user_id) VALUES($1) ON CONFLICT DO NOTHING", user_id
        )


async def unfreeze_user(user_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM frozen_users WHERE user_id=$1", user_id)


async def get_frozen_users():
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM frozen_users")
        return [r["user_id"] for r in rows]


async def is_frozen(user_id: int) -> bool:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM frozen_users WHERE user_id=$1", user_id)
        return row is not None


# ---------- wallet ----------

async def get_user_wallet(user_id: int) -> dict:
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT bees, farms, boosts, username FROM users WHERE user_id=$1", user_id
        )
        bees = int(row["bees"])
        return {
            "bees": bees,
            "honey": bees / 1000.0,
            "farms": int(row["farms"]),
            "boosts": int(row["boosts"]),
            "username": row["username"],
        }


async def add_bees_to_user(user_id: int, n: int):
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET bees = bees + $1 WHERE user_id=$2", n, user_id)


async def deduct_bees(user_id: int, n: int) -> bool:
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT bees FROM users WHERE user_id=$1", user_id)
        if not row or int(row["bees"]) < n:
            return False
        await conn.execute("UPDATE users SET bees = bees - $1 WHERE user_id=$2", n, user_id)
        return True


async def add_honey_to_user(user_id: int, amount: float):
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET honey = honey + $1 WHERE user_id=$2", amount, user_id)


async def deduct_honey(user_id: int, amount: float) -> bool:
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT honey FROM users WHERE user_id=$1", user_id)
        if not row or float(row["honey"]) + 1e-9 < amount:
            return False
        await conn.execute("UPDATE users SET honey = honey - $1 WHERE user_id=$2", amount, user_id)
        return True


async def add_farms(user_id: int, n: int):
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET farms = farms + $1 WHERE user_id=$2", n, user_id)


async def add_boosts(user_id: int, n: int):
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET boosts = boosts + $1 WHERE user_id=$2", n, user_id)


async def update_username(user_id: int, username: Optional[str]):
    await ensure_user(user_id)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET username=$1 WHERE user_id=$2", username, user_id)


async def find_user_by_username(username: str) -> Optional[int]:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM users WHERE lower(username)=lower($1)", username
        )
        return row["user_id"] if row else None


async def log_transfer(sender: int, recipient: int, recipient_username: Optional[str], amount: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO transfers_log(sender, recipient, recipient_username, amount) VALUES($1,$2,$3,$4)",
            sender, recipient, recipient_username, amount,
        )


async def is_new_player(user_id: int) -> bool:
    """Новичок: < 10 000 пчол и < 2 авто-ферм."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT bees, farms FROM users WHERE user_id=$1", user_id)
    if not row:
        return True
    return int(row["bees"] or 0) < 10000 and int(row["farms"] or 0) < 2
