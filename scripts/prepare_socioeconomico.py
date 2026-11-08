#!/usr/bin/env python3
"""Inventaria e gera CSVs processados de PIB (IBGE) + IDHM (Atlas) para Base 4."""

from __future__ import annotations

import csv
import re
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_PIB_ZIP = ROOT / "data" / "raw" / "ibge" / "pib_municipios" / "base_de_dados_2010_2023_txt.zip"
RAW_IDHM_2010 = ROOT / "data" / "raw" / "atlas" / "idhm" / "dados2010_nasa_hackathon.csv"
RAW_IDHM_MULTI = ROOT / "data" / "raw" / "atlas" / "idhm" / "idh_municipios_atlas.csv"
REF_MUN = ROOT / "data" / "processed" / "ibge" / "ref_municipio.csv"
OUT_DIR = ROOT / "data" / "processed" / "socioeconomico"
OUT_PIB = OUT_DIR / "ref_pib_municipio.csv"
OUT_IDHM = OUT_DIR / "ref_idhm_municipio.csv"

FONTE_PIB = "IBGE PIB Municípios 2010-2023 (base_de_dados_2010_2023_txt)"
FONTE_IDHM = "Atlas Brasil / PNUD (espelho CSV municipal com código IBGE)"

# Layout fixed-width IBGE (posições 1-based inclusive → Python [start-1:end])
# ver layout_da_base_de_dados_2010_2023_em_formato_txt.pdf
PIB_FIELDS = {
    "ano": (1, 4),
    "id_municipio": (47, 53),
    "vab_agro_mil": (821, 838),
    "vab_industria_mil": (840, 857),
    "vab_servicos_mil": (859, 876),
    "vab_adm_mil": (878, 895),
    "vab_total_mil": (897, 914),
    "impostos_mil": (916, 933),
    "pib_mil": (935, 952),
    "pib_per_capita": (954, 971),
}


def slice_fw(line: str, start: int, end: int) -> str:
    return line[start - 1 : end].strip()


def parse_num(s: str):
    if not s or not s.strip():
        return ""
    return s.strip().replace(",", ".")


def norm_key(nome: str, uf: str) -> str:
    s = unicodedata.normalize("NFKD", nome)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s).upper()
    s = re.sub(r"\s+", " ", s).strip()
    return f"{s}|{uf.upper()}"


def extract_pib_txt() -> Path:
    if not RAW_PIB_ZIP.exists():
        raise SystemExit(f"ZIP PIB ausente: {RAW_PIB_ZIP}")
    tmp = ROOT / "data" / "raw" / "ibge" / "pib_municipios" / "_extracted"
    tmp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RAW_PIB_ZIP) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise SystemExit("Nenhum .txt no ZIP PIB")
        target = names[0]
        out = tmp / Path(target).name
        if not out.exists() or out.stat().st_size < 1_000_000:
            with zf.open(target) as src, out.open("wb") as dst:
                dst.write(src.read())
    return out


def write_pib(txt_path: Path, known_ids: set[str]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = [
        "id_municipio",
        "ano",
        "pib_mil",
        "pib_per_capita",
        "vab_agro_mil",
        "vab_industria_mil",
        "vab_servicos_mil",
        "vab_adm_mil",
        "vab_total_mil",
        "impostos_mil",
        "fonte",
    ]
    n = 0
    skipped = 0
    with txt_path.open("r", encoding="latin-1", newline="") as fin, OUT_PIB.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        w = csv.DictWriter(fout, fieldnames=cols)
        w.writeheader()
        for line in fin:
            if len(line) < 970:
                continue
            row = {k: slice_fw(line, *span) for k, span in PIB_FIELDS.items()}
            mid = row["id_municipio"]
            if not re.fullmatch(r"\d{7}", mid):
                continue
            if mid not in known_ids:
                skipped += 1
                continue
            out = {
                "id_municipio": mid,
                "ano": row["ano"],
                "pib_mil": parse_num(row["pib_mil"]),
                "pib_per_capita": parse_num(row["pib_per_capita"]),
                "vab_agro_mil": parse_num(row["vab_agro_mil"]),
                "vab_industria_mil": parse_num(row["vab_industria_mil"]),
                "vab_servicos_mil": parse_num(row["vab_servicos_mil"]),
                "vab_adm_mil": parse_num(row["vab_adm_mil"]),
                "vab_total_mil": parse_num(row["vab_total_mil"]),
                "impostos_mil": parse_num(row["impostos_mil"]),
                "fonte": FONTE_PIB,
            }
            w.writerow(out)
            n += 1
    print(f"PIB skipped (sem ref.municipio)={skipped}")
    return n


def load_mun_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    with REF_MUN.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            idx[norm_key(row["nome"], row["sigla_uf"])] = row["id_municipio"]
    return idx


def write_idhm(known_ids: set[str], mun_idx: dict[str, str]) -> int:
    """2010 com código IBGE; 1991/2000 via match nome+UF no CSV multi-ano."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = [
        "id_municipio",
        "ano",
        "idhm",
        "idhm_renda",
        "idhm_longevidade",
        "idhm_educacao",
        "fonte",
    ]
    rows: dict[tuple[str, int], dict] = {}

    with RAW_IDHM_2010.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mid = str(row["cod7"]).strip()
            if not re.fullmatch(r"\d{7}", mid) or mid not in known_ids:
                continue
            rows[(mid, 2010)] = {
                "id_municipio": mid,
                "ano": 2010,
                "idhm": row["idhm"],
                "idhm_renda": row["idhm_renda"],
                "idhm_longevidade": row["idhm_longev"],
                "idhm_educacao": row["idhm_edu"],
                "fonte": FONTE_IDHM,
            }

    # Territorialidades;IDHM 1991;...
    with RAW_IDHM_MULTI.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            terr = (row.get("Territorialidades") or "").strip()
            if not terr or terr == "Brasil" or "(" not in terr:
                continue
            m = re.match(r"^(.*)\(([A-Z]{2})\)$", terr.strip())
            if not m:
                continue
            nome, uf = m.group(1).strip(), m.group(2)
            mid = mun_idx.get(norm_key(nome, uf))
            if not mid:
                continue
            for ano, suffix in ((1991, "1991"), (2000, "2000"), (2010, "2010")):
                key = (mid, ano)
                if key in rows and ano == 2010:
                    continue  # mantém a linha com código do espelho 2010
                idhm = (row.get(f"IDHM {suffix}") or "").strip()
                if not idhm:
                    continue
                rows[key] = {
                    "id_municipio": mid,
                    "ano": ano,
                    "idhm": idhm.replace(",", "."),
                    "idhm_renda": (row.get(f"IDHM Renda {suffix}") or "").replace(",", "."),
                    "idhm_longevidade": (
                        row.get(f"IDHM Longevidade {suffix}") or ""
                    ).replace(",", "."),
                    "idhm_educacao": (row.get(f"IDHM Educação {suffix}") or row.get(
                        f"IDHM Educacao {suffix}"
                    ) or "").replace(",", "."),
                    "fonte": FONTE_IDHM,
                }

    with OUT_IDHM.open("w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=cols)
        w.writeheader()
        for key in sorted(rows.keys()):
            w.writerow(rows[key])
    return len(rows)


def main() -> None:
    mun_idx = load_mun_index()
    known_ids = set(mun_idx.values())
    print(f"ref.municipio keys={len(known_ids)}")
    txt = extract_pib_txt()
    n_pib = write_pib(txt, known_ids)
    n_idhm = write_idhm(known_ids, mun_idx)
    print(f"PIB rows={n_pib} → {OUT_PIB}")
    print(f"IDHM rows={n_idhm} → {OUT_IDHM}")


if __name__ == "__main__":
    main()
