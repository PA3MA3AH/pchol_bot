# repositories/checks_repo.py
from typing import Optional

from db.pool import db


async def create_check(creator_id: int, amount: int, recipient_id: Optional[int] = None,
                        recipient_username: Optional[str] = None) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO checks(creator_id, amount, recipient_id, recipient_username)
               VALUES($1,$2,$3,$4) RETURNING id""",
            creator_id, amount, recipient_id, recipient_username,
        )
        return row["id"]


async def get_check(check_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM checks WHERE id=$1", check_id)


async def use_check(check_id: int, user_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE checks SET is_used=TRUE, used_by=$1, used_at=now() WHERE id=$2",
            user_id, check_id,
        )


async def delete_check(check_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM checks WHERE id=$1", check_id)


async def get_user_checks(user_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM checks WHERE creator_id=$1 AND is_used=FALSE ORDER BY id", user_id
        )


async def count_user_checks(user_id: int) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM checks WHERE creator_id=$1 AND is_used=FALSE", user_id
        )
        return row["cnt"] if row else 0
