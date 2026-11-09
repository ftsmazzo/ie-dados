#!/usr/bin/env python3
"""Carga ref.plano_governo a partir do inventário + flag eleito.

Fontes de eleito/nome:
- eleitoral.votacao (Gov/Pref) com DS_SIT_TOT_TURNO ~ '^ELEITO'
- TSE consulta_cand (Presidente incluso) em data/raw/tse/consulta_cand/AAAA/
"""

from __future__ import annotations

import csv
import io
import os
import sys
import zipfile
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
CSV_INV = ROOT / "data" / "processed" / "planos_governo" / "inventario_planos.csv"
RAW_CAND = ROOT / "data" / "raw" / "tse" / "consulta_cand"

CARGO_PRES, CARGO_GOV, CARGO_PREF = 1, 3, 11
ANOS_P0 = [2018, 2020, 2022, 2024, 2026]


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Defina DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    return url


def is_eleito_sit(sit: str | None) -> bool:
    s = (sit or "").strip().upper()
    return s.startswith("ELEITO")  # exclui NÃO ELEITO


def sit_priority(sit: str | None) -> int:
    """Menor = melhor. consulta_cand traz 1º e 2º turno; preferir ELEITO."""
    s = (sit or "").strip().upper()
    if s.startswith("ELEITO"):
        return 0
    if "2" in s and "TURNO" in s:
        return 1
    if s.startswith("NÃO") or s.startswith("NAO"):
        return 3
    if not s or s.startswith("#"):
        return 4
    return 2


def infer_cargo(unidade: str, sg_uf: str | None, ano: int) -> tuple[int | None, str | None]:
    if (unidade or "").upper() == "BR" or sg_uf in (None, "", "BR"):
        return CARGO_PRES, "Presidente"
    if ano in (2020, 2024):
        return CARGO_PREF, "Prefeito"
    if ano in (2018, 2022, 2026):
        return CARGO_GOV, "Governador"
    return None, None


def load_consulta_cand_map(anos: list[int]) -> dict[tuple[int, int], dict]:
    """(ano, sq_candidato) → metadados a partir dos ZIPs consulta_cand."""
    out: dict[tuple[int, int], dict] = {}
    if not RAW_CAND.exists():
        return out

    for ano in anos:
        year_dir = RAW_CAND / str(ano)
        if not year_dir.exists():
            continue
        for zip_path in sorted(year_dir.glob("consulta_cand_*.zip")):
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    base = Path(name).name.upper()
                    if not base.endswith(".CSV"):
                        continue
                    # prefer BRASIL / BR; skip demais se BRASIL existir depois — lemos todos e sobrescreve ok
                    if "BRASIL" not in base and not base.endswith("_BR.CSV"):
                        # ainda ler UFs para Gov/Pref
                        pass
                    raw = zf.read(name)
                    text = raw.decode("latin-1", errors="replace")
                    reader = csv.DictReader(io.StringIO(text), delimiter=";")
                    for row in reader:
                        try:
                            sq = int(row.get("SQ_CANDIDATO") or 0)
                            cd = int(row.get("CD_CARGO") or 0)
                        except ValueError:
                            continue
                        if not sq or cd not in (CARGO_PRES, CARGO_GOV, CARGO_PREF):
                            continue
                        sit = row.get("DS_SIT_TOT_TURNO") or ""
                        sg_uf = (row.get("SG_UF") or "").strip().upper() or None
                        if cd == CARGO_PRES:
                            sg_uf = None
                        id_mun = None
                        # SG_UE municipal: código TSE 5 dígitos — município IBGE resolvido depois se preciso
                        cand = {
                            "cd_cargo": cd,
                            "ds_cargo": row.get("DS_CARGO"),
                            "sg_uf": sg_uf,
                            "id_municipio": id_mun,
                            "nm_candidato": row.get("NM_URNA_CANDIDATO")
                            or row.get("NM_CANDIDATO"),
                            "sg_partido": row.get("SG_PARTIDO"),
                            "ds_sit_tot_turno": sit,
                            "eleito": is_eleito_sit(sit),
                        }
                        prev = out.get((ano, sq))
                        if prev is None or sit_priority(sit) < sit_priority(
                            prev.get("ds_sit_tot_turno")
                        ):
                            out[(ano, sq)] = cand
    return out


def main() -> None:
    if not CSV_INV.exists():
        raise SystemExit("Inventário ausente. Rode inventario_planos_governo.py")

    rows = list(csv.DictReader(CSV_INV.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("Inventário vazio — coloque ZIPs em data/raw/tse/planos_governo/AAAA/")

    cand_csv = load_consulta_cand_map(ANOS_P0)
    print(f"consulta_cand map n={len(cand_csv)}")

    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute((SQL_DIR / "007_planos_governo.sql").read_text(encoding="utf-8"))

            cur.execute(
                """
                SELECT DISTINCT ON (ano_eleicao, sq_candidato)
                  ano_eleicao, sq_candidato, cd_cargo, ds_cargo, sg_uf, id_municipio,
                  nm_urna_candidato, sg_partido, ds_sit_tot_turno,
                  (ds_sit_tot_turno ~* '^ELEITO') AS eleito
                FROM eleitoral.votacao_candidato_munzona
                WHERE sq_candidato IS NOT NULL
                  AND cd_cargo IN (%s, %s, %s)
                  AND ano_eleicao = ANY(%s)
                ORDER BY ano_eleicao, sq_candidato,
                  CASE WHEN ds_sit_tot_turno ~* '^ELEITO' THEN 0 ELSE 1 END,
                  nr_turno DESC
                """,
                (CARGO_PRES, CARGO_GOV, CARGO_PREF, ANOS_P0),
            )
            cand: dict[tuple[int, int], dict] = {}
            for r in cur.fetchall():
                cand[(int(r[0]), int(r[1]))] = {
                    "cd_cargo": r[2],
                    "ds_cargo": r[3],
                    "sg_uf": r[4],
                    "id_municipio": r[5],
                    "nm_candidato": r[6],
                    "sg_partido": r[7],
                    "ds_sit_tot_turno": r[8],
                    "eleito": bool(r[9]),
                }

            # consulta_cand enriquece (tem Presidente); preferir melhor DS_SIT_TOT_TURNO
            for k, v in cand_csv.items():
                base = cand.get(k, {})
                if not base:
                    cand[k] = v
                    continue
                merged = {**base}
                for kk, vv in v.items():
                    if vv in (None, ""):
                        continue
                    if kk == "ds_sit_tot_turno":
                        if sit_priority(vv) < sit_priority(merged.get("ds_sit_tot_turno")):
                            merged["ds_sit_tot_turno"] = vv
                            merged["eleito"] = is_eleito_sit(vv)
                    elif kk == "eleito":
                        merged["eleito"] = merged.get("eleito") or bool(vv)
                    else:
                        merged[kk] = vv
                if is_eleito_sit(merged.get("ds_sit_tot_turno")):
                    merged["eleito"] = True
                cand[k] = merged

            cur.execute("TRUNCATE docs.plano_chunk, ref.plano_governo RESTART IDENTITY CASCADE")

            batch = []
            for row in rows:
                ano = int(row["ano_eleicao"])
                sq = int(row["sq_candidato"])
                unidade = (row.get("unidade_arquivo") or "").upper()
                sg_csv = (row.get("sg_uf") or "").strip().upper() or None
                if sg_csv == "BR":
                    sg_csv = None

                info = cand.get((ano, sq), {})
                cd_cargo, ds_cargo = infer_cargo(unidade, sg_csv, ano)
                if info.get("cd_cargo"):
                    cd_cargo = info["cd_cargo"]
                    ds_cargo = info.get("ds_cargo") or ds_cargo

                sg_uf = info.get("sg_uf") or sg_csv
                id_mun = info.get("id_municipio")
                if cd_cargo == CARGO_PRES:
                    sg_uf = None
                    id_mun = None
                elif cd_cargo == CARGO_GOV:
                    id_mun = None

                batch.append(
                    (
                        ano,
                        cd_cargo,
                        ds_cargo,
                        sg_uf,
                        id_mun,
                        sq,
                        info.get("nm_candidato"),
                        info.get("sg_partido"),
                        bool(info.get("eleito", False)),
                        info.get("ds_sit_tot_turno"),
                        row["arquivo_nome"],
                        row.get("arquivo_sha256") or None,
                        row.get("url_origem") or None,
                        row.get("path_raw") or None,
                    )
                )

            execute_batch(
                cur,
                """
                INSERT INTO ref.plano_governo (
                  ano_eleicao, cd_cargo, ds_cargo, sg_uf, id_municipio,
                  sq_candidato, nm_candidato, sg_partido, eleito, ds_sit_tot_turno,
                  arquivo_nome, arquivo_sha256, url_origem, path_raw
                ) VALUES (
                  %s,%s,%s,%s,%s,
                  %s,%s,%s,%s,%s,
                  %s,%s,%s,%s
                )
                ON CONFLICT (ano_eleicao, sq_candidato, arquivo_nome) DO UPDATE SET
                  eleito = EXCLUDED.eleito,
                  ds_sit_tot_turno = EXCLUDED.ds_sit_tot_turno,
                  nm_candidato = COALESCE(EXCLUDED.nm_candidato, ref.plano_governo.nm_candidato),
                  sg_partido = COALESCE(EXCLUDED.sg_partido, ref.plano_governo.sg_partido),
                  cd_cargo = COALESCE(EXCLUDED.cd_cargo, ref.plano_governo.cd_cargo),
                  ds_cargo = COALESCE(EXCLUDED.ds_cargo, ref.plano_governo.ds_cargo),
                  id_municipio = COALESCE(EXCLUDED.id_municipio, ref.plano_governo.id_municipio),
                  loaded_at = now()
                """,
                batch,
                page_size=500,
            )

            cur.execute(
                """
                SELECT
                  COUNT(*) AS n,
                  COUNT(*) FILTER (WHERE eleito) AS n_eleito,
                  COUNT(*) FILTER (WHERE ano_eleicao = 2026 AND cd_cargo = 1) AS n_pres_2026,
                  COUNT(*) FILTER (WHERE ano_eleicao = 2026 AND eleito AND cd_cargo = 1) AS n_pres_2026_eleito,
                  MAX(nm_candidato) FILTER (
                    WHERE ano_eleicao = 2026 AND eleito AND cd_cargo = 1
                  ) AS pres_2026_nome
                FROM ref.plano_governo
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
        "loaded planos",
        {
            "n": stats[0],
            "n_eleito": stats[1],
            "n_pres_2026": stats[2],
            "n_pres_2026_eleito": stats[3],
            "pres_2026_nome": stats[4],
        },
    )


if __name__ == "__main__":
    main()
