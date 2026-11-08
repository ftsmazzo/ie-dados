#!/usr/bin/env python3
"""Carga Base 1: municípios (DTB) + população (estimativas IBGE) no Postgres."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
CSV_MUN = ROOT / "data" / "processed" / "ibge" / "ref_municipio.csv"
CSV_POP = ROOT / "data" / "processed" / "ibge" / "ref_populacao_municipio.csv"


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
        # skip header for COPY
        header = next(csv.reader(f))
        if header != columns:
            raise SystemExit(f"CSV header mismatch in {path}: {header} != {columns}")
        cur.copy_expert(
            sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
                sql.SQL(table), cols
            ).as_string(cur),
            f,
        )
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.SQL(table)))
    return int(cur.fetchone()[0])


def main() -> None:
    if not CSV_MUN.exists() or not CSV_POP.exists():
        raise SystemExit("CSVs processados ausentes. Rode a preparação antes.")

    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            run_sql_file(cur, SQL_DIR / "000_extensions.sql")
            run_sql_file(cur, SQL_DIR / "001_ref_municipios.sql")
            cur.execute("TRUNCATE ref.populacao_municipio, ref.municipio")

            n_mun = copy_csv(
                cur,
                "ref.municipio",
                CSV_MUN,
                [
                    "id_municipio",
                    "nome",
                    "sigla_uf",
                    "codigo_uf",
                    "nome_uf",
                    "id_regiao_intermediaria",
                    "nome_regiao_intermediaria",
                    "id_regiao_imediata",
                    "nome_regiao_imediata",
                    "fonte",
                    "data_referencia",
                ],
            )
            n_pop = copy_csv(
                cur,
                "ref.populacao_municipio",
                CSV_POP,
                ["id_municipio", "ano", "populacao", "fonte", "data_referencia"],
            )

            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM ref.municipio) AS n_mun,
                  (SELECT COUNT(*) FROM ref.populacao_municipio) AS n_pop,
                  (SELECT COUNT(*) FROM ref.municipio m
                     LEFT JOIN ref.populacao_municipio p
                       ON p.id_municipio = m.id_municipio AND p.ano = 2024
                    WHERE p.id_municipio IS NULL) AS mun_sem_pop,
                  (SELECT COUNT(DISTINCT sigla_uf) FROM ref.municipio) AS n_ufs,
                  (SELECT MIN(populacao) FROM ref.populacao_municipio WHERE ano = 2024) AS pop_min,
                  (SELECT SUM(populacao::bigint) FROM ref.populacao_municipio WHERE ano = 2024) AS pop_sum
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
            "municipios": n_mun,
            "populacao_rows": n_pop,
            "stats": {
                "n_mun": stats[0],
                "n_pop": stats[1],
                "mun_sem_pop": stats[2],
                "n_ufs": stats[3],
                "pop_min": stats[4],
                "pop_sum": stats[5],
            },
        }
    )


if __name__ == "__main__":
    main()
