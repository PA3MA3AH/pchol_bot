# repositories/cards_repo.py
import random

from db.pool import db
from constants import CARD_CLASSES, CLASS_BASES


async def init_card_catalog():
    """Заполняет card_catalog 100 карточками насекомых (идемпотентно)."""
    async with db.pool.acquire() as conn:
        for cls, names in CARD_CLASSES.items():
            base = CLASS_BASES[cls]
            for i, name in enumerate(names, start=1):
                cid = f"{cls[:3]}_{i:02d}"
                hp = int(base["hp"] * random.uniform(0.9, 1.1))
                atk = int(base["atk"] * random.uniform(0.9, 1.1))
                heal = int(base["heal"] * random.uniform(0.9, 1.1))
                support = int(base["support"] * random.uniform(0.9, 1.1))
                defense = int(base["def"] * random.uniform(0.9, 1.1))
                await conn.execute(
                    """
                    INSERT INTO card_catalog(
                        card_id, class, name, description, base_hp, base_atk, base_heal, base_support, base_defense
                    )
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (card_id) DO NOTHING
                    """,
                    cid, cls, name, f"Карточка {name} класса {cls}", hp, atk, heal, support, defense,
                )


async def get_all_card_ids():
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT card_id FROM card_catalog")
        return [r["card_id"] for r in rows]


async def get_card_names(card_ids: list) -> dict:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT card_id, name FROM card_catalog WHERE card_id = ANY($1::text[])", card_ids
        )
        return {r["card_id"]: r["name"] for r in rows}


async def user_has_card(user_id: int, card_id: str):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT instance_id, level FROM user_cards WHERE user_id=$1 AND card_id=$2 LIMIT 1",
            user_id, card_id,
        )


async def add_user_card(user_id: int, card_id: str, level: int = 1) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO user_cards(user_id, card_id, level) VALUES($1,$2,$3) RETURNING instance_id",
            user_id, card_id, level,
        )
        return row["instance_id"]


async def get_user_cards(user_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """SELECT uc.instance_id, uc.level, c.card_id, c.name, c.class
               FROM user_cards uc
               JOIN card_catalog c ON c.card_id = uc.card_id
               WHERE uc.user_id=$1
               ORDER BY uc.instance_id DESC""",
            user_id,
        )


async def get_card_instance(instance_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT user_id, level FROM user_cards WHERE instance_id=$1", instance_id
        )


async def set_card_level(instance_id: int, level: int):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE user_cards SET level=$1 WHERE instance_id=$2", level, instance_id)


async def get_cards_by_instance_ids(instance_ids: list):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            "SELECT instance_id, user_id, level FROM user_cards WHERE instance_id = ANY($1::bigint[])",
            instance_ids,
        )


async def delete_cards(instance_ids: list):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_cards WHERE instance_id = ANY($1::bigint[])", instance_ids
        )


async def owns_cards(user_id: int, instance_ids: list) -> bool:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT instance_id FROM user_cards WHERE user_id=$1 AND instance_id = ANY($2::bigint[])",
            user_id, instance_ids,
        )
        return len(rows) == len(instance_ids)


async def get_defense_deck(user_id: int) -> list:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT card_ids FROM player_defense_cards WHERE user_id=$1", user_id
        )
        return row["card_ids"] if row else []


async def get_attack_deck(user_id: int) -> list:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT card_ids FROM player_attack_cards WHERE user_id=$1", user_id
        )
        return row["card_ids"] if row else []


async def get_cards_full(instance_ids: list):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """SELECT uc.instance_id, uc.level, c.card_id, c.name, c.class,
                       c.base_hp, c.base_atk, c.base_heal, c.base_support, c.base_defense
               FROM user_cards uc
               JOIN card_catalog c ON c.card_id = uc.card_id
               WHERE uc.instance_id = ANY($1::bigint[])
            """,
            instance_ids,
        )


async def save_defense_deck(user_id: int, card_ids: list):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO player_defense_cards (user_id, card_ids, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE SET card_ids = EXCLUDED.card_ids, updated_at = NOW()
            """,
            user_id, card_ids,
        )


async def save_attack_deck(user_id: int, card_ids: list):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO player_attack_cards (user_id, card_ids, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE SET card_ids = EXCLUDED.card_ids, updated_at = NOW()
            """,
            user_id, card_ids,
        )
