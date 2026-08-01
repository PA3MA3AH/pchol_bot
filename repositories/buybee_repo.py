# repositories/buybee_repo.py
from db.pool import db


async def create_buybee_request(user_id: int, username: str, amount: int, price: float) -> int:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO buybee_requests(user_id, username, amount, price_rub) VALUES($1,$2,$3,$4) RETURNING id",
            user_id, username, amount, price,
        )
        return row["id"]


async def update_buybee_status(req_id: int, status: str):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE buybee_requests SET status=$1 WHERE id=$2", status, req_id)


async def get_buybee_request(req_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM buybee_requests WHERE id=$1", req_id)
