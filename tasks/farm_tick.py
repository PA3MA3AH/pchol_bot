# tasks/farm_tick.py
import asyncio
import logging

from db.pool import db

logger = logging.getLogger("pchol_bot.tasks.farm_tick")


async def farm_tick():
    while True:
        try:
            async with db.pool.acquire() as conn:
                # Одним массовым запросом начисляем доход всем фермерам
                await conn.execute(
                    """
                    UPDATE users
                    SET bees = bees + GREATEST(0, ROUND(farms * (2.0 + 0.5 * boosts)))
                    WHERE farms > 0
                    """
                )
            await asyncio.sleep(60)
        except Exception:
            logger.exception("farm_tick error")
            await asyncio.sleep(60)
