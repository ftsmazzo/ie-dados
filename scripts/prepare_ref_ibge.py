#!/usr/bin/env python3
"""Gera CSVs processados a partir dos arquivos oficiais IBGE em data/raw."""

from __future__ import annotations

import csv
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parents[1]
DTB = (
    ROOT
    / "data"
    / "raw"
    / "ibge"
    / "municipios"
    / "extracted"
    / "RELATORIO_DTB_BRASIL_2025_MUNICIPIOS.xls"
)
POP = ROOT / "data" / "raw" / "ibge" / "populacao" / "POP2024_20241230.xls"
OUT = ROOT / "data" / "processed" / "ibge"


def _cell_str(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def main() -> None:
    if not DTB.exists():
        raise SystemExit(f"DTB ausente: {DTB}")
    if not POP.exists():
        raise SystemExit(f"População ausente: {POP}")

    OUT.mkdir(parents=True, exist_ok=True)

    book = xlrd.open_workbook(str(DTB))
    sh = book.sheet_by_index(0)
    municipios = []
    for r in range(7, sh.nrows):
        codigo_uf = _cell_str(sh.cell_value(r, 0)).zfill(2)
        id_municipio = _cell_str(sh.cell_value(r, 7)).zfill(7)
        municipios.append(
            {
                "id_municipio": id_municipio,
                "nome": _cell_str(sh.cell_value(r, 8)),
                "codigo_uf": codigo_uf,
                "nome_uf": _cell_str(sh.cell_value(r, 1)),
                "id_regiao_intermediaria": _cell_str(sh.cell_value(r, 2)),
                "nome_regiao_intermediaria": _cell_str(sh.cell_value(r, 3)),
                "id_regiao_imediata": _cell_str(sh.cell_value(r, 4)),
                "nome_regiao_imediata": _cell_str(sh.cell_value(r, 5)),
                "fonte": "IBGE DTB 2025",
                "data_referencia": "2025-12-31",
            }
        )

    pb = xlrd.open_workbook(str(POP))
    psh = pb.sheet_by_index(1)
    sigla_by_uf: dict[str, str] = {}
    populacao = []
    for r in range(2, psh.nrows):
        pop = psh.cell_value(r, 4)
        if not isinstance(pop, (int, float)):
            continue
        uf = _cell_str(psh.cell_value(r, 0))
        cod_uf = _cell_str(psh.cell_value(r, 1)).zfill(2)
        cod_m = _cell_str(psh.cell_value(r, 2)).zfill(5)
        id_municipio = cod_uf + cod_m
        sigla_by_uf[cod_uf] = uf
        populacao.append(
            {
                "id_municipio": id_municipio,
                "ano": 2024,
                "populacao": int(pop),
                "fonte": "IBGE Estimativas POP2024_20241230",
                "data_referencia": "2024-07-01",
            }
        )

    for m in municipios:
        m["sigla_uf"] = sigla_by_uf[m["codigo_uf"]]

    mun_path = OUT / "ref_municipio.csv"
    mun_fields = [
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
    ]
    with mun_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=mun_fields)
        w.writeheader()
        w.writerows(municipios)

    pop_path = OUT / "ref_populacao_municipio.csv"
    pop_fields = ["id_municipio", "ano", "populacao", "fonte", "data_referencia"]
    with pop_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pop_fields)
        w.writeheader()
        w.writerows(populacao)

    ids_m = {m["id_municipio"] for m in municipios}
    ids_p = {p["id_municipio"] for p in populacao}
    print(
        {
            "municipios": len(municipios),
            "populacao": len(populacao),
            "only_dtb": len(ids_m - ids_p),
            "only_pop": len(ids_p - ids_m),
            "out": str(OUT),
        }
    )


if __name__ == "__main__":
    main()
