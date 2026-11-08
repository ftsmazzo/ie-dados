from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from ie_dados_mcp import db
from ie_dados_mcp.limits import SAMPLE_SIZE


def save_artifact(
    *,
    kind: str,
    title: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> str:
    row = db.fetch_one(
        """
        INSERT INTO mcp.artifact (kind, title, columns, n_rows, sample_rows, rows_json, meta)
        VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        RETURNING id::text AS id
        """,
        (
            kind,
            title,
            json.dumps(columns, ensure_ascii=False),
            len(rows),
            json.dumps(rows[:SAMPLE_SIZE], ensure_ascii=False, default=str),
            json.dumps(rows, ensure_ascii=False, default=str),
            json.dumps(meta or {}, ensure_ascii=False, default=str),
        ),
    )
    assert row
    return row["id"]


def artifact_get(
    artifact_id: str,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """Lê artefato intermediário já materializado no servidor.

    WHEN TO USE: depois que election_aggregate devolveu artifact_id.
    WHEN NOT TO USE: não invente IDs; só use o retornado pelas tools.
    COST: cheap.
    """
    if offset < 0:
        raise ValueError("offset >= 0")
    if limit < 1 or limit > 200:
        raise ValueError("limit entre 1 e 200")

    # validate uuid
    try:
        UUID(artifact_id)
    except ValueError as e:
        raise ValueError("artifact_id inválido") from e

    row = db.fetch_one(
        """
        SELECT id::text AS id, kind, title, columns, n_rows, sample_rows, rows_json, meta,
               created_at, expires_at
        FROM mcp.artifact
        WHERE id = %s::uuid AND expires_at > now()
        """,
        (artifact_id,),
    )
    if not row:
        raise ValueError("Artefato não encontrado ou expirado")

    all_rows = row["rows_json"]
    if isinstance(all_rows, str):
        all_rows = json.loads(all_rows)
    page = all_rows[offset : offset + limit]
    columns = row["columns"]
    if isinstance(columns, str):
        columns = json.loads(columns)
    sample = row["sample_rows"]
    if isinstance(sample, str):
        sample = json.loads(sample)
    meta = row["meta"]
    if isinstance(meta, str):
        meta = json.loads(meta)

    return {
        "artifact_id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "n_rows": row["n_rows"],
        "columns": columns,
        "sample": sample,
        "page": page,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < int(row["n_rows"]),
        "meta": meta,
        "expires_at": str(row["expires_at"]),
        "cost": "cheap",
    }
