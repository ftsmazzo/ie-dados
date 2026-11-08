from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
import psycopg2.extras


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definido")
    return url


@contextmanager
def connect() -> Iterator[Any]:
    conn = psycopg2.connect(database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def ensure_schema() -> None:
    schema_path = os.environ.get(
        "MCP_SCHEMA_SQL",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "sql", "003_mcp.sql"),
    )
    # Prefer packaged SQL next to repo root when running in Docker: bake SQL into image
    candidates = [
        schema_path,
        "/app/sql/003_mcp.sql",
        os.path.join(os.path.dirname(__file__), "sql", "003_mcp.sql"),
    ]
    sql_text = None
    for path in candidates:
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                sql_text = f.read()
            break
    if sql_text is None:
        # fallback inline
        sql_text = """
        CREATE SCHEMA IF NOT EXISTS mcp;
        CREATE TABLE IF NOT EXISTS mcp.artifact (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind TEXT NOT NULL,
            title TEXT,
            columns JSONB NOT NULL DEFAULT '[]'::jsonb,
            n_rows INTEGER NOT NULL DEFAULT 0,
            sample_rows JSONB NOT NULL DEFAULT '[]'::jsonb,
            rows_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
        );
        CREATE INDEX IF NOT EXISTS idx_mcp_artifact_expires ON mcp.artifact (expires_at);
        """
    execute(sql_text)
