# services/economy.py
import time
from typing import Dict, Tuple

from aiogram.types import Message

from config import BEE, RATE_WINDOW, MAX_BEES_PER_WINDOW, BEEFARM_BASE_PRICE

_user_rate: Dict[int, list] = {}


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


def can_receive_bees(user_id: int, incoming: int) -> Tuple[bool, int]:
    """Скользящее окно RATE_WINDOW секунд, максимум MAX_BEES_PER_WINDOW пчол."""
    now = int(time.time())
    arr = _user_rate.setdefault(user_id, [])
    while arr and arr[0][0] <= now - RATE_WINDOW:
        arr.pop(0)
    current = sum(x[1] for x in arr)
    space = MAX_BEES_PER_WINDOW - current
    accept = max(0, min(space, incoming))
    if accept > 0:
        arr.append((now, accept))
    return accept > 0, accept


def beefarm_total_cost(existing_farms: int, n: int) -> int:
    """Цена n следующих ферм: каждая следующая в 2 раза дороже предыдущей."""
    return sum(BEEFARM_BASE_PRICE * (2 ** (existing_farms + i)) for i in range(n))
