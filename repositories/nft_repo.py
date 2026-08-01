# repositories/nft_repo.py
import json

from db.pool import db

MAX_NFT_PER_USER = 5
MAX_NFT_TOTAL = 150


async def count_user_nfts(user_id: int) -> int:
    async with db.pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM nfts WHERE owner=$1", user_id)


async def count_total_nfts() -> int:
    async with db.pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM nfts")


async def create_nft(owner: int, name: str, metadata: dict) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO nfts(owner, name, metadata) VALUES($1,$2,$3) RETURNING nft_id",
            owner, name, json.dumps(metadata),
        )
        return row["nft_id"]


async def get_nft(nft_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM nfts WHERE nft_id=$1", nft_id)


async def transfer_nft(nft_id: int, from_user: int, to_user: int):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE nfts SET owner=$1 WHERE nft_id=$2", to_user, nft_id)
        await conn.execute(
            "INSERT INTO nft_transfers(nft_id, from_user, to_user) VALUES($1,$2,$3)",
            nft_id, from_user, to_user,
        )


async def update_nft_metadata(nft_id: int, metadata: dict):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE nfts SET metadata=$1 WHERE nft_id=$2", json.dumps(metadata), nft_id
        )


# ---------- marketplace ----------

async def is_listed(nft_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow("SELECT id FROM nft_marketplace WHERE nft_id=$1", nft_id)


async def list_nft(nft_id: int, seller: int, price: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO nft_marketplace(nft_id, seller, price_bees) VALUES($1,$2,$3)",
            nft_id, seller, price,
        )


async def unlist_nft(nft_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM nft_marketplace WHERE nft_id=$1", nft_id)


async def get_listing_by_nft(nft_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT seller, price_bees FROM nft_marketplace WHERE nft_id=$1", nft_id
        )


async def get_marketplace_listings(limit: int = 100):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT m.id AS lot_id, m.nft_id, m.seller, m.price_bees, n.name, n.metadata
            FROM nft_marketplace m
            JOIN nfts n ON n.nft_id = m.nft_id
            ORDER BY m.created_at DESC
            LIMIT $1
            """,
            limit,
        )


async def buy_lot_atomic(lot_id: int, buyer: int):
    """Атомарная покупка NFT с биржи. Возвращает dict с результатом или None если не удалось."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            lot = await conn.fetchrow(
                "SELECT id, nft_id, seller, price_bees FROM nft_marketplace WHERE id=$1 FOR UPDATE",
                lot_id,
            )
            if not lot:
                return {"error": "not_found"}
            if lot["seller"] == buyer:
                return {"error": "own_lot"}

            price = int(lot["price_bees"])
            row_bal = await conn.fetchrow("SELECT bees FROM users WHERE user_id=$1 FOR UPDATE", buyer)
            bal = int(row_bal["bees"]) if row_bal else 0
            if bal < price:
                return {"error": "insufficient_funds"}

            await conn.execute("UPDATE users SET bees = bees - $1 WHERE user_id=$2", price, buyer)
            await conn.execute("UPDATE users SET bees = bees + $1 WHERE user_id=$2", price, lot["seller"])
            await conn.execute("UPDATE nfts SET owner=$1 WHERE nft_id=$2", buyer, lot["nft_id"])
            await conn.execute(
                "INSERT INTO nft_transfers(nft_id, from_user, to_user) VALUES($1,$2,$3)",
                lot["nft_id"], lot["seller"], buyer,
            )
            await conn.execute("DELETE FROM nft_marketplace WHERE id=$1", lot_id)

            return {
                "error": None,
                "nft_id": lot["nft_id"],
                "seller": lot["seller"],
                "price": price,
            }


# ---------- achievements ----------

async def grant_achievement_if_new(user_id: int, key: str) -> bool:
    """Возвращает True, если достижение было новым (и его выдали)."""
    async with db.pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM user_achievements WHERE user_id=$1 AND achv_key=$2", user_id, key
        )
        if exists:
            return False
        await conn.execute(
            "INSERT INTO user_achievements(user_id, achv_key) VALUES($1,$2)", user_id, key
        )
        return True


async def get_user_achievements(user_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            "SELECT achv_key, achieved_at FROM user_achievements WHERE user_id=$1", user_id
        )
