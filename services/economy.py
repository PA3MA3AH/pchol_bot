# services/economy.py
import time
from typing import Tuple

from aiogram.types import Message

from config import BEE, RATE_WINDOW, MAX_BEES_PER_WINDOW, BEEFARM_BASE_PRICE
from db.pool import db


def count_bees_in_message(msg: Message) -> int:
    count = 0
    if msg.text:
        count += msg.text.count(BEE)
    if msg.caption:
        count += msg.caption.count(BEE)
    sticker = getattr(msg, "sticker", None)
    if sticker and getattr(sticker, "emoji", None):
        count += sticker.emoji.count(BEE)
    return count


async def can_receive_bees(user_id: int, incoming: int) -> Tuple[bool, int]:
    """Скользящее окно RATE_WINDOW секунд, максимум MAX_BEES_PER_WINDOW пчол."""
    now = int(time.time())
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT window_start, total_bees FROM user_rate_limits WHERE user_id=$1",
            user_id,
        )
        if row:
            window_start = int(row["window_start"])
            total = int(row["total_bees"])
            if now - window_start >= RATE_WINDOW:
                # Окно истекло, сбрасываем
                await conn.execute(
                    "INSERT INTO user_rate_limits (user_id, window_start, total_bees) VALUES ($1, $2, $3) "
                    "ON CONFLICT (user_id) DO UPDATE SET window_start=EXCLUDED.window_start, total_bees=EXCLUDED.total_bees",
                    user_id, now, 0,
                )
                total = 0
            space = MAX_BEES_PER_WINDOW - total
            accept = max(0, min(space, incoming))
            if accept > 0:
                await conn.execute(
                    "UPDATE user_rate_limits SET total_bees = total_bees + $1 WHERE user_id=$2",
                    accept, user_id,
                )
            return accept > 0, accept
        else:
            # Первый раз
            accept = min(MAX_BEES_PER_WINDOW, incoming)
            await conn.execute(
                "INSERT INTO user_rate_limits (user_id, window_start, total_bees) VALUES ($1, $2, $3)",
                user_id, now, accept,
            )
            return accept > 0, accept


def beefarm_total_cost(existing_farms: int, n: int) -> int:
    """Цена n следующих ферм: каждая следующая в 2 раза дороже предыдущей."""
    return sum(BEEFARM_BASE_PRICE * (2 ** (existing_farms + i)) for i in range(n))
