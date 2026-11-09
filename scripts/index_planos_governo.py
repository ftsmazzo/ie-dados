#!/usr/bin/env python3
"""Extrai texto dos PDFs de planos e indexa chunks (eleitos primeiro; Pres 2026 no topo)."""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

ROOT = Path(__file__).resolve().parents[1]
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Defina DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    return url


def extract_text_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError as e:
            raise SystemExit("Instale pypdf: pip install pypdf") from e

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(t)
    text = "\n".join(parts)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(n, i + CHUNK_SIZE)
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        i = max(end - CHUNK_OVERLAP, i + 1)
    return chunks


def read_pdf_bytes(path_raw: str, arquivo_nome: str) -> bytes | None:
    full = ROOT / path_raw
    if full.is_file() and full.suffix.lower() == ".pdf":
        return full.read_bytes()
    if full.is_file() and full.suffix.lower() == ".zip":
        with zipfile.ZipFile(full) as zf:
            for name in zf.namelist():
                if Path(name).name == arquivo_nome:
                    return zf.read(name)
    # fallback: procurar zip na pasta do ano
    m = re.match(r".*/(\d{4})/", path_raw.replace("\\", "/"))
    if m:
        year_dir = ROOT / "data" / "raw" / "tse" / "planos_governo" / m.group(1)
        if year_dir.exists():
            for zip_path in year_dir.glob("*.zip"):
                with zipfile.ZipFile(zip_path) as zf:
                    for name in zf.namelist():
                        if Path(name).name == arquivo_nome:
                            return zf.read(name)
            for pdf in year_dir.rglob(arquivo_nome):
                return pdf.read_bytes()
    return None


def main() -> None:
    limit = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit = int(sys.argv[1])

    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    indexed = 0
    skipped = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id_plano, ano_eleicao, cd_cargo, eleito, arquivo_nome, path_raw
                FROM ref.plano_governo
                ORDER BY
                  CASE WHEN ano_eleicao = 2026 AND cd_cargo = 1 AND eleito THEN 0
                       WHEN eleito THEN 1
                       ELSE 2 END,
                  ano_eleicao DESC,
                  id_plano
                """
            )
            planos = cur.fetchall()
            if limit:
                planos = planos[:limit]

            for id_plano, ano, cd_cargo, eleito, arquivo_nome, path_raw in planos:
                data = read_pdf_bytes(path_raw or "", arquivo_nome)
                if not data:
                    skipped += 1
                    print(f"skip missing pdf id={id_plano} {arquivo_nome}")
                    continue
                text = extract_text_pdf(data)
                chunks = chunk_text(text)
                cur.execute("DELETE FROM docs.plano_chunk WHERE id_plano = %s", (id_plano,))
                if chunks:
                    execute_batch(
                        cur,
                        """
                        INSERT INTO docs.plano_chunk (id_plano, chunk_ord, secao, texto)
                        VALUES (%s, %s, %s, %s)
                        """,
                        [
                            (id_plano, i, f"chunk_{i}", c)
                            for i, c in enumerate(chunks)
                        ],
                        page_size=100,
                    )
                cur.execute(
                    """
                    UPDATE ref.plano_governo
                    SET n_chunks = %s, indexado_em = now()
                    WHERE id_plano = %s
                    """,
                    (len(chunks), id_plano),
                )
                indexed += 1
                flag = "ELEITO" if eleito else "candidato"
                print(
                    f"indexed id={id_plano} ano={ano} cargo={cd_cargo} "
                    f"{flag} chunks={len(chunks)} {arquivo_nome}"
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print({"indexed": indexed, "skipped": skipped})


if __name__ == "__main__":
    main()
