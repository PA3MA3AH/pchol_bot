# repositories/polls_repo.py
from datetime import datetime

from db.pool import db


async def create_poll(creator_id: int, chat_id: int, poll_id: str, message_id: int,
                       question: str, options: str, correct_ids: str, allow_multiple: bool,
                       prize: int, end_time: datetime) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO polls(creator_id, chat_id, poll_id, message_id, question, options,
               correct_option_ids, allow_multiple, prize_bees, end_time)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id""",
            creator_id, chat_id, poll_id, message_id, question, options,
            correct_ids, allow_multiple, prize, end_time,
        )
        return row["id"]


async def get_poll_by_id(poll_id: str):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM polls WHERE poll_id=$1", poll_id)


async def close_poll(poll_db_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE polls SET is_closed=TRUE WHERE id=$1", poll_db_id)


async def add_poll_vote(poll_db_id: int, user_id: int, option_ids: str):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO poll_votes(poll_db_id, user_id, option_ids) VALUES($1,$2,$3)
               ON CONFLICT DO NOTHING""",
            poll_db_id, user_id, option_ids,
        )


async def get_poll_votes(poll_db_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM poll_votes WHERE poll_db_id=$1", poll_db_id)


async def mark_vote_rewarded(vote_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE poll_votes SET rewarded=TRUE WHERE id=$1", vote_id)


async def get_expired_polls():
    """Опросы с истёкшим сроком, которые ещё не закрыты."""
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT * FROM polls
            WHERE end_time IS NOT NULL
              AND end_time <= NOW()
              AND is_closed = FALSE
            """
        )
