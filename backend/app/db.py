"""Postgres access: one connection pool and plain SQL, no ORM."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

type Pool = AsyncConnectionPool
type Row = dict[str, Any]


async def open_pool(database_url: str) -> Pool:
    pool = AsyncConnectionPool(database_url, min_size=1, max_size=10, open=False)
    await pool.open(wait=True, timeout=30)
    return pool


async def apply_schema(pool: Pool) -> None:
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_PATH.read_text())


async def fetch_all(pool: Pool, sql: str, params: Sequence[Any] = ()) -> list[Row]:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetch_one(pool: Pool, sql: str, params: Sequence[Any] = ()) -> Row | None:
    rows = await fetch_all(pool, sql, params)
    return rows[0] if rows else None


def to_pgvector(vector: list[float]) -> str:
    """Format a vector as the text literal pgvector parses: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"
