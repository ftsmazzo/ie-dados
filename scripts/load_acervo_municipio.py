#!/usr/bin/env python3
"""Carrega MD do acervo municipal → docs.municipio_doc + docs.municipio_chunk (FTS)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "008_acervo_municipio.sql"
ACERVOS = ROOT / "docs" / "acervos" / "municipios"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

# slug pasta → id_municipio IBGE
MUNICIPIOS = {
    "ribeirao-preto": "3543402",
}


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Defina DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    return url


def chunk_text(text: str) -> list[str]:
    text = (text or "").replace("\x00", "").strip()
    if not text:
        return []
    chunks: list[str] = []
    i, n = 0, len(text)
    while i < n:
        end = min(n, i + CHUNK_SIZE)
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        i = max(end - CHUNK_OVERLAP, i + 1)
    return chunks


def infer_tipo(rel: str) -> tuple[str, str | None]:
    rel = rel.replace("\\", "/")
    if rel.startswith("secretarias/"):
        slug = Path(rel).stem
        return "secretaria", slug
    if rel.startswith("servicos/"):
        # servicos/{secretaria}-...
        name = Path(rel).stem
        sec = name.split("-", 1)[0] if "-" in name else None
        return "servico", sec
    if rel.startswith("00-autoridades"):
        return "autoridade", None
    if rel == "README.md":
        return "institucional", None
    return "institucional", None


def title_from_md(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def load_municipio(cur, slug_mun: str, id_mun: str) -> dict:
    base = ACERVOS / slug_mun
    if not base.exists():
        raise SystemExit(f"Pasta ausente: {base}")

    manifest_path = base / "_meta" / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # remove docs anteriores deste município
    cur.execute(
        "DELETE FROM docs.municipio_doc WHERE id_municipio = %s",
        (id_mun,),
    )

    n_docs = 0
    n_chunks = 0
    md_files = sorted(base.rglob("*.md"))
    for path in md_files:
        if "_meta" in path.parts:
            continue
        rel = str(path.relative_to(base)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        tipo, sec = infer_tipo(rel)
        titulo = title_from_md(text, path.stem)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # url fonte: primeira URL nas Fontes do MD, ou manifest
        url_fonte = None
        m = re.search(r"^## Fontes\s*\n((?:- .+\n?)+)", text, re.M)
        if m:
            first = re.search(r"https?://\S+", m.group(1))
            if first:
                url_fonte = first.group(0).rstrip(").,")

        scraped_at = manifest.get("scraped_at")
        cur.execute(
            """
            INSERT INTO docs.municipio_doc (
              id_municipio, slug_municipio, secretaria_slug, tipo, titulo,
              path_md, url_fonte, sha256, scraped_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id_doc
            """,
            (
                id_mun,
                slug_mun,
                sec,
                tipo,
                titulo,
                rel,
                url_fonte,
                sha,
                scraped_at,
            ),
        )
        id_doc = cur.fetchone()[0]
        chunks = chunk_text(text)
        if chunks:
            execute_batch(
                cur,
                """
                INSERT INTO docs.municipio_chunk (id_doc, chunk_ord, secao, texto)
                VALUES (%s,%s,%s,%s)
                """,
                [(id_doc, i, f"chunk_{i}", c) for i, c in enumerate(chunks)],
                page_size=100,
            )
        cur.execute(
            """
            UPDATE docs.municipio_doc
            SET n_chunks = %s, indexado_em = now()
            WHERE id_doc = %s
            """,
            (len(chunks), id_doc),
        )
        n_docs += 1
        n_chunks += len(chunks)
        print(f"  {rel} tipo={tipo} chunks={len(chunks)}")

    return {"slug": slug_mun, "id_municipio": id_mun, "n_docs": n_docs, "n_chunks": n_chunks}


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    targets = {only: MUNICIPIOS[only]} if only else MUNICIPIOS
    if only and only not in MUNICIPIOS:
        raise SystemExit(f"Município desconhecido: {only}. Conhecidos: {sorted(MUNICIPIOS)}")

    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(SQL.read_text(encoding="utf-8"))
            results = []
            for slug, mid in targets.items():
                print(f"== {slug} ==")
                results.append(load_municipio(cur, slug, mid))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print({"loaded": results})


if __name__ == "__main__":
    main()
