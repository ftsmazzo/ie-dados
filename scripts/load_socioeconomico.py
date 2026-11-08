#!/usr/bin/env python3
"""Carga Base 4: ref.pib_municipio + ref.idhm_municipio."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
CSV_PIB = ROOT / "data" / "processed" / "socioeconomico" / "ref_pib_municipio.csv"
CSV_IDHM = ROOT / "data" / "processed" / "socioeconomico" / "ref_idhm_municipio.csv"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Defina DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    return url


def run_sql_file(cur, path: Path) -> None:
    cur.execute(path.read_text(encoding="utf-8"))


def copy_csv(cur, table: str, path: Path, columns: list[str]) -> int:
    cols = sql.SQL(", ").join(map(sql.Identifier, columns))
    with path.open("r", encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
        if header != columns:
            raise SystemExit(f"CSV header mismatch in {path}: {header} != {columns}")
        cur.copy_expert(
            sql.SQL(
                "COPY {} ({}) FROM STDIN WITH (FORMAT csv, NULL '')"
            ).format(sql.SQL(table), cols).as_string(cur),
            f,
        )
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.SQL(table)))
    return int(cur.fetchone()[0])


def main() -> None:
    if not CSV_PIB.exists() or not CSV_IDHM.exists():
        raise SystemExit("CSVs processados ausentes. Rode prepare_socioeconomico.py primeiro.")

    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            run_sql_file(cur, SQL_DIR / "006_socioeconomico.sql")
            cur.execute("TRUNCATE ref.pib_municipio, ref.idhm_municipio")

            n_pib = copy_csv(
                cur,
                "ref.pib_municipio",
                CSV_PIB,
                [
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
                ],
            )
            n_idhm = copy_csv(
                cur,
                "ref.idhm_municipio",
                CSV_IDHM,
                [
                    "id_municipio",
                    "ano",
                    "idhm",
                    "idhm_renda",
                    "idhm_longevidade",
                    "idhm_educacao",
                    "fonte",
                ],
            )

            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM ref.pib_municipio) AS n_pib,
                  (SELECT COUNT(DISTINCT ano) FROM ref.pib_municipio) AS n_anos_pib,
                  (SELECT COUNT(DISTINCT id_municipio) FROM ref.pib_municipio WHERE ano = 2023) AS mun_pib_2023,
                  (SELECT COUNT(*) FROM ref.idhm_municipio) AS n_idhm,
                  (SELECT COUNT(*) FROM ref.idhm_municipio WHERE ano = 2010) AS idhm_2010,
                  (SELECT COUNT(*) FROM ref.idhm_municipio WHERE ano = 2000) AS idhm_2000,
                  (SELECT COUNT(*) FROM ref.idhm_municipio WHERE ano = 1991) AS idhm_1991,
                  (SELECT COUNT(*) FROM ref.pib_municipio p
                     LEFT JOIN ref.municipio m ON m.id_municipio = p.id_municipio
                    WHERE m.id_municipio IS NULL) AS pib_orfao,
                  (SELECT COUNT(*) FROM ref.idhm_municipio i
                     LEFT JOIN ref.municipio m ON m.id_municipio = i.id_municipio
                    WHERE m.id_municipio IS NULL) AS idhm_orfao
                """
            )
            stats = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    labels = [
        "n_pib",
        "n_anos_pib",
        "mun_pib_2023",
        "n_idhm",
        "idhm_2010",
        "idhm_2000",
        "idhm_1991",
        "pib_orfao",
        "idhm_orfao",
    ]
    print("loaded", dict(zip(labels, stats)))
    print(f"copy counts pib={n_pib} idhm={n_idhm}")


if __name__ == "__main__":
    main()
