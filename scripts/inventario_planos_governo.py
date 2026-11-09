#!/usr/bin/env python3
"""Inventaria PDFs de proposta_governo (ZIP ou pasta) → CSV processado."""

from __future__ import annotations

import csv
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "tse" / "planos_governo"
OUT = ROOT / "data" / "processed" / "planos_governo" / "inventario_planos.csv"

# 2026BR280002538811_01.pdf | 2018BR280000601016.pdf | 2024SP250002140500_01.pdf
PDF_RE = re.compile(
    r"^(?P<ano>\d{4})(?P<ue>[A-Z]{2})(?P<sq>\d+)(?:_(?P<seq>\d+))?\.pdf$",
    re.IGNORECASE,
)

ANOS_P0 = {2018, 2020, 2022, 2024, 2026}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_name(name: str) -> dict | None:
    base = Path(name).name
    m = PDF_RE.match(base)
    if not m:
        return None
    ue = m.group("ue").upper()
    return {
        "ano_eleicao": int(m.group("ano")),
        "sg_uf": None if ue == "BR" else ue,
        "unidade_arquivo": ue,
        "sq_candidato": int(m.group("sq")),
        "arquivo_nome": base,
        "seq_arquivo": int(m.group("seq") or 1),
    }


def iter_pdfs_from_zip(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".pdf"):
                continue
            name = Path(info.filename).name
            if name.lower() == "leiame.pdf":
                continue
            meta = parse_name(name)
            if not meta:
                continue
            if meta["ano_eleicao"] not in ANOS_P0:
                continue
            data = zf.read(info)
            meta.update(
                {
                    "arquivo_sha256": sha256_bytes(data),
                    "path_raw": str(zip_path.relative_to(ROOT)).replace("\\", "/"),
                    "url_origem": (
                        "https://cdn.tse.jus.br/estatistica/sead/odsele/proposta_governo/"
                        + zip_path.name
                    ),
                    "bytes": len(data),
                }
            )
            yield meta


def iter_pdfs_from_dir(year_dir: Path):
    for pdf in year_dir.rglob("*.pdf"):
        if pdf.name.lower() == "leiame.pdf":
            continue
        meta = parse_name(pdf.name)
        if not meta or meta["ano_eleicao"] not in ANOS_P0:
            continue
        data = pdf.read_bytes()
        meta.update(
            {
                "arquivo_sha256": sha256_bytes(data),
                "path_raw": str(pdf.relative_to(ROOT)).replace("\\", "/"),
                "url_origem": "",
                "bytes": len(data),
            }
        )
        yield meta


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"Pasta raw ausente: {RAW}")

    rows: dict[tuple, dict] = {}
    for year_dir in sorted(RAW.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for zip_path in sorted(year_dir.glob("*.zip")):
            for meta in iter_pdfs_from_zip(zip_path):
                key = (meta["ano_eleicao"], meta["sq_candidato"], meta["arquivo_nome"])
                rows[key] = meta
        # PDFs soltos / extraídos
        for meta in iter_pdfs_from_dir(year_dir):
            key = (meta["ano_eleicao"], meta["sq_candidato"], meta["arquivo_nome"])
            rows.setdefault(key, meta)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "ano_eleicao",
        "sg_uf",
        "unidade_arquivo",
        "sq_candidato",
        "arquivo_nome",
        "seq_arquivo",
        "arquivo_sha256",
        "path_raw",
        "url_origem",
        "bytes",
    ]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for key in sorted(rows.keys()):
            w.writerow({c: rows[key].get(c, "") for c in cols})

    print(f"inventario n={len(rows)} → {OUT}")


if __name__ == "__main__":
    main()
