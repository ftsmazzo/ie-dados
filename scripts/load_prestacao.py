#!/usr/bin/env python3
"""Carga Base 3 P0: receitas, despesas contratadas/pagas e doador originário.

Uso:
  python scripts/load_prestacao.py                 # tudo, todos os anos P0
  python scripts/load_prestacao.py 2024            # um ano, kinds default
  python scripts/load_prestacao.py --kinds=pagas,doador 2020 2022
Kinds: receita, despesa, pagas, doador (default: receita,despesa)
"""

from __future__ import annotations

import csv
import io
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SQL_CORE = ROOT / "sql" / "004_financeiro.sql"
SQL_EXT = ROOT / "sql" / "005_financeiro_ext.sql"
RAW = ROOT / "data" / "raw" / "tse" / "prestacao"
YEARS = [2018, 2020, 2022, 2024, 2026]
CHUNK = 200_000

SKIP_UF = {"BRASIL", "BR"}
KIND_RECEITA = "receitas_candidatos"
KIND_DESPESA = "despesas_contratadas_candidatos"
KIND_PAGAS = "despesas_pagas_candidatos"
KIND_DOADOR = "receitas_candidatos_doador_originario"
NAME_RE = re.compile(
    r"^(?P<kind>.+)_(?P<year>\d{4})_(?P<uf>[A-Za-z]+)\.csv$", re.I
)
ALL_KINDS = ("receita", "despesa", "pagas", "doador")


def _int(v):
    if v is None:
        return None
    s = str(v).strip().strip('"')
    if s == "" or s.upper() in {"#NULO", "#NE", "NA", "N/A", "-1"}:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return None


def _txt(v):
    if v is None:
        return None
    s = str(v).replace("\x00", "").strip().strip('"')
    if s == "" or s.upper() in {"#NULO", "#NE"}:
        return None
    return s


def _money(v):
    if v is None:
        return None
    s = str(v).strip().strip('"')
    if s == "" or s.upper() in {"#NULO", "#NE"}:
        return None
    s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") > 1 else s
    # padrão BR: 10000,00 ou 1.234.567,89
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return None


def _date(v):
    s = _txt(v)
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _ue_tse(sg_ue: str | None) -> int | None:
    """SG_UE numérico = código município TSE; UF/BR = sem município."""
    if not sg_ue:
        return None
    s = sg_ue.strip()
    if not s.isdigit():
        return None
    return int(s)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL")
    return url


def find_zip(year: int) -> Path:
    for base in (RAW / str(year) / "candidatos", RAW / str(year)):
        zips = sorted(base.glob("*.zip"))
        if zips:
            return zips[0]
    raise FileNotFoundError(f"ZIP prestação {year} não encontrado em {RAW}/{year}")


def load_mapping(cur) -> dict[int, str]:
    cur.execute("SELECT cd_municipio_tse, id_municipio FROM ref.municipio_tse")
    return {int(a): str(b) for a, b in cur.fetchall() if a is not None and b}


def iter_kind_rows(zpath: Path, year: int, kind_prefix: str):
    with zipfile.ZipFile(zpath) as z:
        members = []
        for name in z.namelist():
            if not name.lower().endswith(".csv"):
                continue
            base = Path(name).name
            m = NAME_RE.match(base)
            if not m:
                continue
            if int(m.group("year")) != year:
                continue
            if m.group("kind").lower() != kind_prefix:
                continue
            uf = m.group("uf").upper()
            if uf in SKIP_UF:
                continue
            members.append(name)
        for name in sorted(members):
            with z.open(name) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                reader = csv.DictReader(text, delimiter=";")
                for row in reader:
                    out = {}
                    for k, v in row.items():
                        if not k:
                            continue
                        key = k.strip().strip('"').replace("\x00", "")
                        if isinstance(v, str):
                            v = v.replace("\x00", "")
                        out[key] = v
                    yield out


def flush_copy(cur, table: str, cols: str, buf: io.StringIO) -> None:
    data = buf.getvalue()
    if not data:
        return
    bio = io.StringIO(data)
    cur.copy_expert(
        f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')",
        bio,
    )


def load_receitas_year(cur, year: int, mapping: dict[int, str]) -> int:
    zpath = find_zip(year)
    part = f"financeiro.receita_candidato_{year}"
    cur.execute(f"TRUNCATE {part}")
    cols = """
      ano_eleicao, nr_turno, cd_eleicao, sg_uf, sg_ue, nm_ue,
      cd_municipio_tse, id_municipio, cd_cargo, ds_cargo,
      sq_candidato, nr_candidato, nm_candidato, nr_partido, sg_partido,
      cd_fonte_receita, ds_fonte_receita, cd_origem_receita, ds_origem_receita,
      cd_natureza_receita, ds_natureza_receita, nr_cpf_cnpj_doador, nm_doador,
      sq_receita, dt_receita, vr_receita
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    total = 0
    for row in iter_kind_rows(zpath, year, KIND_RECEITA):
        sg_ue = _txt(row.get("SG_UE"))
        cd_tse = _ue_tse(sg_ue)
        w.writerow(
            [
                _int(row.get("AA_ELEICAO")) or year,
                _int(row.get("ST_TURNO")),
                _int(row.get("CD_ELEICAO")),
                _txt(row.get("SG_UF")),
                sg_ue,
                _txt(row.get("NM_UE")),
                cd_tse,
                mapping.get(cd_tse) if cd_tse is not None else None,
                _int(row.get("CD_CARGO")),
                _txt(row.get("DS_CARGO")),
                _int(row.get("SQ_CANDIDATO")),
                _int(row.get("NR_CANDIDATO")),
                _txt(row.get("NM_CANDIDATO")),
                _int(row.get("NR_PARTIDO")),
                _txt(row.get("SG_PARTIDO")),
                _int(row.get("CD_FONTE_RECEITA")),
                _txt(row.get("DS_FONTE_RECEITA")),
                _int(row.get("CD_ORIGEM_RECEITA")),
                _txt(row.get("DS_ORIGEM_RECEITA")),
                _int(row.get("CD_NATUREZA_RECEITA")),
                _txt(row.get("DS_NATUREZA_RECEITA")),
                _txt(row.get("NR_CPF_CNPJ_DOADOR")),
                _txt(row.get("NM_DOADOR")),
                _int(row.get("SQ_RECEITA")),
                _date(row.get("DT_RECEITA")),
                _money(row.get("VR_RECEITA")),
            ]
        )
        total += 1
        if total % CHUNK == 0:
            flush_copy(cur, part, cols, buf)
            buf = io.StringIO()
            w = csv.writer(buf)
            print(f"  receita {year}: {total} ...", flush=True)
    flush_copy(cur, part, cols, buf)
    return total


def load_pagas_year(cur, year: int) -> int:
    zpath = find_zip(year)
    part = f"financeiro.despesa_paga_candidato_{year}"
    cur.execute(f"TRUNCATE {part}")
    cols = """
      ano_eleicao, nr_turno, cd_eleicao, sg_uf,
      cd_fonte_despesa, ds_fonte_despesa, cd_origem_despesa, ds_origem_despesa,
      cd_natureza_despesa, ds_natureza_despesa, sq_despesa, sq_parcelamento_despesa,
      dt_pagto_despesa, ds_despesa, vr_pagto_despesa
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    total = 0
    for row in iter_kind_rows(zpath, year, KIND_PAGAS):
        w.writerow(
            [
                _int(row.get("AA_ELEICAO")) or year,
                _int(row.get("ST_TURNO")),
                _int(row.get("CD_ELEICAO")),
                _txt(row.get("SG_UF")),
                _int(row.get("CD_FONTE_DESPESA")),
                _txt(row.get("DS_FONTE_DESPESA")),
                _int(row.get("CD_ORIGEM_DESPESA")),
                _txt(row.get("DS_ORIGEM_DESPESA")),
                _int(row.get("CD_NATUREZA_DESPESA")),
                _txt(row.get("DS_NATUREZA_DESPESA")),
                _int(row.get("SQ_DESPESA")),
                _int(row.get("SQ_PARCELAMENTO_DESPESA")),
                _date(row.get("DT_PAGTO_DESPESA")),
                _txt(row.get("DS_DESPESA")),
                _money(row.get("VR_PAGTO_DESPESA")),
            ]
        )
        total += 1
        if total % CHUNK == 0:
            flush_copy(cur, part, cols, buf)
            buf = io.StringIO()
            w = csv.writer(buf)
            print(f"  paga {year}: {total} ...", flush=True)
    flush_copy(cur, part, cols, buf)
    return total


def load_doador_year(cur, year: int) -> int:
    zpath = find_zip(year)
    part = f"financeiro.receita_doador_originario_{year}"
    cur.execute(f"TRUNCATE {part}")
    cols = """
      ano_eleicao, nr_turno, cd_eleicao, sg_uf,
      nr_cpf_cnpj_doador_originario, nm_doador_originario, tp_doador_originario,
      cd_cnae_doador_originario, ds_cnae_doador_originario,
      sq_receita, dt_receita, ds_receita, vr_receita
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    total = 0
    for row in iter_kind_rows(zpath, year, KIND_DOADOR):
        w.writerow(
            [
                _int(row.get("AA_ELEICAO")) or year,
                _int(row.get("ST_TURNO")),
                _int(row.get("CD_ELEICAO")),
                _txt(row.get("SG_UF")),
                _txt(row.get("NR_CPF_CNPJ_DOADOR_ORIGINARIO")),
                _txt(row.get("NM_DOADOR_ORIGINARIO")),
                _txt(row.get("TP_DOADOR_ORIGINARIO")),
                _int(row.get("CD_CNAE_DOADOR_ORIGINARIO")),
                _txt(row.get("DS_CNAE_DOADOR_ORIGINARIO")),
                _int(row.get("SQ_RECEITA")),
                _date(row.get("DT_RECEITA")),
                _txt(row.get("DS_RECEITA")),
                _money(row.get("VR_RECEITA")),
            ]
        )
        total += 1
        if total % CHUNK == 0:
            flush_copy(cur, part, cols, buf)
            buf = io.StringIO()
            w = csv.writer(buf)
            print(f"  doador {year}: {total} ...", flush=True)
    flush_copy(cur, part, cols, buf)
    return total


def load_despesas_year(cur, year: int, mapping: dict[int, str]) -> int:
    zpath = find_zip(year)
    part = f"financeiro.despesa_contratada_candidato_{year}"
    cur.execute(f"TRUNCATE {part}")
    cols = """
      ano_eleicao, nr_turno, cd_eleicao, sg_uf, sg_ue, nm_ue,
      cd_municipio_tse, id_municipio, cd_cargo, ds_cargo,
      sq_candidato, nr_candidato, nm_candidato, nr_partido, sg_partido,
      cd_origem_despesa, ds_origem_despesa, nm_fornecedor,
      sq_despesa, dt_despesa, vr_despesa_contratada
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    total = 0
    for row in iter_kind_rows(zpath, year, KIND_DESPESA):
        sg_ue = _txt(row.get("SG_UE"))
        cd_tse = _ue_tse(sg_ue)
        w.writerow(
            [
                _int(row.get("AA_ELEICAO")) or year,
                _int(row.get("ST_TURNO")),
                _int(row.get("CD_ELEICAO")),
                _txt(row.get("SG_UF")),
                sg_ue,
                _txt(row.get("NM_UE")),
                cd_tse,
                mapping.get(cd_tse) if cd_tse is not None else None,
                _int(row.get("CD_CARGO")),
                _txt(row.get("DS_CARGO")),
                _int(row.get("SQ_CANDIDATO")),
                _int(row.get("NR_CANDIDATO")),
                _txt(row.get("NM_CANDIDATO")),
                _int(row.get("NR_PARTIDO")),
                _txt(row.get("SG_PARTIDO")),
                _int(row.get("CD_ORIGEM_DESPESA")),
                _txt(row.get("DS_ORIGEM_DESPESA")),
                _txt(row.get("NM_FORNECEDOR")),
                _int(row.get("SQ_DESPESA")),
                _date(row.get("DT_DESPESA")),
                _money(row.get("VR_DESPESA_CONTRATADA")),
            ]
        )
        total += 1
        if total % CHUNK == 0:
            flush_copy(cur, part, cols, buf)
            buf = io.StringIO()
            w = csv.writer(buf)
            print(f"  despesa {year}: {total} ...", flush=True)
    flush_copy(cur, part, cols, buf)
    return total


def parse_args(argv: list[str]) -> tuple[list[int], set[str]]:
    kinds = {"receita", "despesa"}
    years: list[int] = []
    for a in argv:
        if a.startswith("--kinds="):
            raw = a.split("=", 1)[1].strip().lower()
            if raw in {"all", "*"}:
                kinds = set(ALL_KINDS)
            else:
                kinds = {k.strip() for k in raw.split(",") if k.strip()}
            bad = kinds - set(ALL_KINDS)
            if bad:
                raise SystemExit(f"kinds inválidos: {bad}. Use {ALL_KINDS}")
        elif a.isdigit():
            years.append(int(a))
        else:
            raise SystemExit(f"Argumento inválido: {a}")
    return (years or list(YEARS)), kinds


def main() -> None:
    years, kinds = parse_args(sys.argv[1:])
    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            print("Applying DDL...", flush=True)
            cur.execute(SQL_CORE.read_text(encoding="utf-8"))
            cur.execute(SQL_EXT.read_text(encoding="utf-8"))
            mapping = load_mapping(cur)
            print(f"  crosswalk entries={len(mapping)} kinds={sorted(kinds)}", flush=True)
            conn.commit()

            for y in years:
                zname = find_zip(y).name
                if "receita" in kinds:
                    print(f"Loading receitas {y} from {zname} ...", flush=True)
                    n_r = load_receitas_year(cur, y, mapping)
                    conn.commit()
                    print(f"  receita {y} rows={n_r}", flush=True)
                if "despesa" in kinds:
                    print(f"Loading despesas contratadas {y} ...", flush=True)
                    n_d = load_despesas_year(cur, y, mapping)
                    conn.commit()
                    print(f"  despesa {y} rows={n_d}", flush=True)
                if "pagas" in kinds:
                    print(f"Loading despesas pagas {y} ...", flush=True)
                    n_p = load_pagas_year(cur, y)
                    conn.commit()
                    print(f"  paga {y} rows={n_p}", flush=True)
                if "doador" in kinds:
                    print(f"Loading doador originario {y} ...", flush=True)
                    n_o = load_doador_year(cur, y)
                    conn.commit()
                    print(f"  doador {y} rows={n_o}", flush=True)

            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM financeiro.receita_candidato) AS n_rec,
                  (SELECT COUNT(*) FROM financeiro.despesa_contratada_candidato) AS n_desp,
                  (SELECT COUNT(*) FROM financeiro.despesa_paga_candidato) AS n_paga,
                  (SELECT COALESCE(SUM(vr_pagto_despesa),0) FROM financeiro.despesa_paga_candidato) AS soma_paga,
                  (SELECT COUNT(*) FROM financeiro.receita_doador_originario) AS n_doador,
                  (SELECT COALESCE(SUM(vr_receita),0) FROM financeiro.receita_doador_originario) AS soma_doador
                """
            )
            stats = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        "OK Base 3 extensão:",
        {
            "n_receitas": stats[0],
            "n_despesas_contratadas": stats[1],
            "n_despesas_pagas": stats[2],
            "soma_pagas": float(stats[3]),
            "n_doador_originario": stats[4],
            "soma_doador": float(stats[5]),
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
