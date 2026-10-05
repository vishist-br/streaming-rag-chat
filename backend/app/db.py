"""Postgres access: one connection pool and plain SQL, no ORM."""

from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

type Pool = AsyncConnectionPool


async def open_pool(database_url: str) -> Pool:
    pool = AsyncConnectionPool(
        database_url,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open(wait=True, timeout=30)
    return pool


async def apply_schema(pool: Pool) -> None:
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_PATH.read_text())


def to_pgvector(vector: list[float]) -> str:
    """Format a vector as the text literal pgvector parses: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


def from_pgvector(literal: str) -> list[float]:
    return [float(x) for x in literal.strip("[]").split(",")]
