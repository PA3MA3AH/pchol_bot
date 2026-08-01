# db/pool.py
import logging
import os
from typing import Optional

import asyncpg

from config import DATABASE_URL, DB_MIN_SIZE, DB_MAX_SIZE

logger = logging.getLogger("pchol_bot.db")

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class DB:
    """Тонкая обёртка над пулом asyncpg. Всю бизнес-логику/запросы храним
    в repositories/*, здесь только подключение и общие low-level методы."""

    def __init__(self):
        self.pool: Optional[asyncpg.pool.Pool] = None

    async def connect(self):
        logger.info("Connecting to database...")
        self.pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=DB_MIN_SIZE,
            max_size=DB_MAX_SIZE,
        )
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)
            # чистим нулевые записи сообщений (как и в оригинале)
            await conn.execute("DELETE FROM messages WHERE bees_count = 0;")

        logger.info("DB ready.")

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None


db = DB()
