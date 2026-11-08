#!/usr/bin/env python3
"""Carga Base 2: cruzamento TSE/IBGE + detalhe + votação mun/zona (colunas essenciais)."""

from __future__ import annotations

import csv
import io
import os
import sys
import zipfile
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "002_eleitoral.sql"
CROSS = (
    ROOT
    / "data"
    / "raw"
    / "tse"
    / "cruzamento"
    / "extracted"
    / "municipio_tse_ibge.csv"
)
URNA = ROOT / "data" / "raw" / "tse" / "urna"
YEARS = [1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026]

VOT_COLS = [
    "ANO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "CD_CARGO",
    "DS_CARGO",
    "SQ_CANDIDATO",
    "NR_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "NR_PARTIDO",
    "SG_PARTIDO",
    "QT_VOTOS_NOMINAIS",
    "QT_VOTOS_NOMINAIS_VALIDOS",
    "DS_SIT_TOT_TURNO",
]

DET_COLS = [
    "ANO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "CD_CARGO",
    "DS_CARGO",
    "QT_APTOS",
    "QT_COMPARECIMENTO",
    "QT_ABSTENCOES",
    "QT_TOTAL_VOTOS_VALIDOS",
    "QT_VOTOS_BRANCOS",
    "QT_VOTOS_NULOS",
]


def _int(v):
    if v is None:
        return None
    s = str(v).strip().strip('"')
    if s == "" or s.upper() in {"#NULO", "#NE", "NA", "N/A"}:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _txt(v):
    if v is None:
        return None
    s = str(v).strip().strip('"')
    if s == "" or s.upper() in {"#NULO", "#NE"}:
        return None
    return s


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL")
    return url


def load_crosswalk(cur, mapping_out: dict[int, str]) -> int:
    cur.execute("TRUNCATE ref.municipio_tse")
    rows = []
    with CROSS.open(encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            cd_tse = _int(r["CD_MUNICIPIO_TSE"])
            id_ibge = _txt(r["CD_MUNICIPIO_IBGE"])
            if cd_tse is None or not id_ibge:
                continue
            id_ibge = id_ibge.zfill(7)
            sg = _txt(r["SG_UF"]) or ""
            rows.append(
                (
                    cd_tse,
                    id_ibge,
                    sg,
                    _txt(r["NM_MUNICIPIO_TSE"]),
                    _txt(r["NM_MUNICIPIO_IBGE"]),
                )
            )
            mapping_out[cd_tse] = id_ibge

    buf = io.StringIO()
    w = csv.writer(buf)
    for row in rows:
        w.writerow(row)
    buf.seek(0)
    cur.copy_expert(
        """
        COPY ref.municipio_tse (cd_municipio_tse, id_municipio, sg_uf, nm_municipio_tse, nm_municipio_ibge)
        FROM STDIN WITH (FORMAT csv)
        """,
        buf,
    )
    return len(rows)


def iter_zip_dicts(zpath: Path):
    with zipfile.ZipFile(zpath) as z:
        csvs = [
            n
            for n in z.namelist()
            if n.lower().endswith(".csv")
            and not n.upper().endswith(("BRASIL.CSV", "BR.CSV"))
        ]
        for name in sorted(csvs):
            with z.open(name) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                reader = csv.DictReader(text, delimiter=";")
                # normalize keys without quotes
                for row in reader:
                    yield {k.strip().strip('"'): v for k, v in row.items()}


def load_detalhe(cur, mapping: dict[int, str]) -> int:
    cur.execute("TRUNCATE eleitoral.detalhe_munzona")
    total = 0
    buf = io.StringIO()
    w = csv.writer(buf)
    for y in YEARS:
        zpath = URNA / str(y) / "detalhe_votacao_munzona" / f"detalhe_votacao_munzona_{y}.zip"
        if not zpath.exists():
            raise FileNotFoundError(zpath)
        for row in iter_zip_dicts(zpath):
            cd_tse = _int(row.get("CD_MUNICIPIO"))
            # QT_VOTOS_NULOS vs QT_TOTAL_VOTOS_NULOS
            nulos = row.get("QT_VOTOS_NULOS")
            if nulos is None or str(nulos).strip() == "":
                nulos = row.get("QT_TOTAL_VOTOS_NULOS")
            w.writerow(
                [
                    _int(row.get("ANO_ELEICAO")),
                    _int(row.get("NR_TURNO")),
                    _int(row.get("CD_ELEICAO")),
                    _txt(row.get("SG_UF")),
                    cd_tse,
                    mapping.get(cd_tse) if cd_tse is not None else None,
                    _int(row.get("NR_ZONA")),
                    _int(row.get("CD_CARGO")),
                    _txt(row.get("DS_CARGO")),
                    _int(row.get("QT_APTOS")),
                    _int(row.get("QT_COMPARECIMENTO")),
                    _int(row.get("QT_ABSTENCOES")),
                    _int(row.get("QT_TOTAL_VOTOS_VALIDOS")),
                    _int(row.get("QT_VOTOS_BRANCOS")),
                    _int(nulos),
                ]
            )
            total += 1
            if total % 200_000 == 0:
                print(f"  detalhe rows buffered {total} ...", flush=True)
    buf.seek(0)
    cur.copy_expert(
        """
        COPY eleitoral.detalhe_munzona (
          ano_eleicao, nr_turno, cd_eleicao, sg_uf, cd_municipio_tse, id_municipio,
          nr_zona, cd_cargo, ds_cargo, qt_aptos, qt_comparecimento, qt_abstencoes,
          qt_total_votos_validos, qt_votos_brancos, qt_votos_nulos
        ) FROM STDIN WITH (FORMAT csv, NULL '')
        """,
        buf,
    )
    return total


def load_votacao_year(cur, year: int, mapping: dict[int, str]) -> int:
    zpath = (
        URNA
        / str(year)
        / "votacao_candidato_munzona"
        / f"votacao_candidato_munzona_{year}.zip"
    )
    if not zpath.exists():
        raise FileNotFoundError(zpath)
    cur.execute(
        f"TRUNCATE eleitoral.votacao_candidato_munzona_{year}"
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    total = 0
    for row in iter_zip_dicts(zpath):
        cd_tse = _int(row.get("CD_MUNICIPIO"))
        w.writerow(
            [
                _int(row.get("ANO_ELEICAO")) or year,
                _int(row.get("NR_TURNO")),
                _int(row.get("CD_ELEICAO")),
                _txt(row.get("SG_UF")),
                cd_tse,
                mapping.get(cd_tse) if cd_tse is not None else None,
                _int(row.get("NR_ZONA")),
                _int(row.get("CD_CARGO")),
                _txt(row.get("DS_CARGO")),
                _int(row.get("SQ_CANDIDATO")),
                _int(row.get("NR_CANDIDATO")),
                _txt(row.get("NM_URNA_CANDIDATO")),
                _int(row.get("NR_PARTIDO")),
                _txt(row.get("SG_PARTIDO")),
                _int(row.get("QT_VOTOS_NOMINAIS")),
                _int(row.get("QT_VOTOS_NOMINAIS_VALIDOS")),
                _txt(row.get("DS_SIT_TOT_TURNO")),
            ]
        )
        total += 1
        if total % 500_000 == 0:
            # flush chunk to DB to keep memory bounded
            buf.seek(0)
            cur.copy_expert(
                f"""
                COPY eleitoral.votacao_candidato_munzona_{year} (
                  ano_eleicao, nr_turno, cd_eleicao, sg_uf, cd_municipio_tse, id_municipio,
                  nr_zona, cd_cargo, ds_cargo, sq_candidato, nr_candidato, nm_urna_candidato,
                  nr_partido, sg_partido, qt_votos_nominais, qt_votos_nominais_validos, ds_sit_tot_turno
                ) FROM STDIN WITH (FORMAT csv, NULL '')
                """,
                buf,
            )
            buf = io.StringIO()
            w = csv.writer(buf)
            print(f"  {year}: loaded {total} rows ...", flush=True)
    if buf.tell() > 0 or total:
        # always copy remaining (including empty-safe)
        data = buf.getvalue()
        if data:
            bio = io.StringIO(data)
            cur.copy_expert(
                f"""
                COPY eleitoral.votacao_candidato_munzona_{year} (
                  ano_eleicao, nr_turno, cd_eleicao, sg_uf, cd_municipio_tse, id_municipio,
                  nr_zona, cd_cargo, ds_cargo, sq_candidato, nr_candidato, nm_urna_candidato,
                  nr_partido, sg_partido, qt_votos_nominais, qt_votos_nominais_validos, ds_sit_tot_turno
                ) FROM STDIN WITH (FORMAT csv, NULL '')
                """,
                bio,
            )
    return total


def main() -> None:
    if not CROSS.exists():
        raise SystemExit(f"Cruzamento ausente: {CROSS}")

    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    mapping: dict[int, str] = {}
    try:
        with conn.cursor() as cur:
            print("Applying DDL...", flush=True)
            cur.execute(SQL.read_text(encoding="utf-8"))
            print("Loading crosswalk...", flush=True)
            n_cross = load_crosswalk(cur, mapping)
            print(f"  municipio_tse={n_cross}", flush=True)
            print("Loading detalhe_munzona...", flush=True)
            n_det = load_detalhe(cur, mapping)
            print(f"  detalhe rows={n_det}", flush=True)
            conn.commit()

            for y in YEARS:
                print(f"Loading votacao {y}...", flush=True)
                n = load_votacao_year(cur, y, mapping)
                conn.commit()
                print(f"  votacao {y} rows={n}", flush=True)

            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM ref.municipio_tse) AS n_cross,
                  (SELECT COUNT(*) FROM ref.municipio_tse t
                     LEFT JOIN ref.municipio m ON m.id_municipio = t.id_municipio
                    WHERE m.id_municipio IS NULL) AS cross_sem_ref,
                  (SELECT COUNT(*) FROM eleitoral.detalhe_munzona) AS n_det,
                  (SELECT COUNT(*) FROM eleitoral.detalhe_munzona WHERE id_municipio IS NULL) AS det_sem_ibge,
                  (SELECT COUNT(*) FROM eleitoral.votacao_candidato_munzona) AS n_vot,
                  (SELECT COUNT(*) FROM eleitoral.votacao_candidato_munzona WHERE id_municipio IS NULL) AS vot_sem_ibge,
                  (SELECT COUNT(DISTINCT ano_eleicao) FROM eleitoral.votacao_candidato_munzona) AS anos_vot
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
        {
            "n_cross": stats[0],
            "cross_sem_ref": stats[1],
            "n_detalhe": stats[2],
            "detalhe_sem_ibge": stats[3],
            "n_votacao": stats[4],
            "votacao_sem_ibge": stats[5],
            "anos_votacao": stats[6],
        }
    )


if __name__ == "__main__":
    main()
