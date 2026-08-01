# tasks/farm_tick.py
import asyncio
import logging

from db.pool import db

logger = logging.getLogger("pchol_bot.tasks.farm_tick")


async def farm_tick():
    while True:
        try:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("SELECT user_id, farms, boosts FROM users WHERE farms > 0")
                for r in rows:
                    farms = int(r["farms"])
                    boosts = int(r["boosts"]) if r["boosts"] is not None else 0
                    per_farm = 2.0 + 0.5 * boosts
                    total_bees = int(per_farm * farms)
                    if total_bees > 0:
                        await conn.execute(
                            "UPDATE users SET bees = bees + $1 WHERE user_id=$2", total_bees, r["user_id"]
                        )
            await asyncio.sleep(60)
        except Exception:
            logger.exception("farm_tick error")
            await asyncio.sleep(60)
