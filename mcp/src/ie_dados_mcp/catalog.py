"""Catálogo lazy de domínios — o agente pede só o que precisa."""

from __future__ import annotations

DOMAINS: dict[str, dict] = {
    "ref": {
        "id": "ref",
        "title": "Referência geográfica e populacional",
        "status": "pronta",
        "cost": "cheap",
        "tables": {
            "ref.municipio": {
                "description": "Municípios IBGE (chave id_municipio CHAR7).",
                "keys": ["id_municipio"],
                "fields": [
                    "id_municipio",
                    "nome",
                    "sigla_uf",
                    "codigo_uf",
                    "nome_uf",
                    "id_regiao_intermediaria",
                    "nome_regiao_intermediaria",
                    "id_regiao_imediata",
                    "nome_regiao_imediata",
                ],
            },
            "ref.populacao_municipio": {
                "description": "População estimada por município/ano.",
                "keys": ["id_municipio", "ano"],
                "fields": ["id_municipio", "ano", "populacao", "fonte", "data_referencia"],
            },
            "ref.municipio_tse": {
                "description": "Cruzamento código TSE ↔ IBGE.",
                "keys": ["cd_municipio_tse"],
                "fields": [
                    "cd_municipio_tse",
                    "id_municipio",
                    "sg_uf",
                    "nm_municipio_tse",
                    "nm_municipio_ibge",
                ],
            },
        },
        "recommended_tools": ["resolve_municipio", "get_populacao"],
    },
    "eleitoral": {
        "id": "eleitoral",
        "title": "Resultados eleitorais município + zona (1998–2026)",
        "status": "pronta",
        "cost": "heavy",
        "tables": {
            "eleitoral.votacao_candidato_munzona": {
                "description": (
                    "Fato de votos nominais (~45M linhas). NUNCA consultar cru. "
                    "Use election_estimate → election_aggregate com group_by + metrics."
                ),
                "keys": ["ano_eleicao", "id_municipio", "nr_zona", "cd_cargo", "sq_candidato"],
                "fields": [
                    "ano_eleicao",
                    "nr_turno",
                    "sg_uf",
                    "id_municipio",
                    "cd_municipio_tse",
                    "nr_zona",
                    "cd_cargo",
                    "ds_cargo",
                    "sg_partido",
                    "nr_partido",
                    "nm_urna_candidato",
                    "sq_candidato",
                    "qt_votos_nominais",
                    "qt_votos_nominais_validos",
                    "ds_sit_tot_turno",
                ],
            },
            "eleitoral.detalhe_munzona": {
                "description": "Aptos/comparecimento/brancos/nulos por mun/zona/cargo.",
                "keys": ["ano_eleicao", "id_municipio", "nr_zona", "cd_cargo", "nr_turno"],
                "fields": [
                    "ano_eleicao",
                    "nr_turno",
                    "sg_uf",
                    "id_municipio",
                    "nr_zona",
                    "cd_cargo",
                    "ds_cargo",
                    "qt_aptos",
                    "qt_comparecimento",
                    "qt_abstencoes",
                    "qt_total_votos_validos",
                    "qt_votos_brancos",
                    "qt_votos_nulos",
                ],
            },
        },
        "recommended_tools": [
            "election_estimate",
            "election_aggregate",
            "artifact_get",
        ],
        "years": [
            1998,
            2000,
            2002,
            2004,
            2006,
            2008,
            2010,
            2012,
            2014,
            2016,
            2018,
            2020,
            2022,
            2024,
            2026,
        ],
    },
}


def list_domains() -> list[dict]:
    return [
        {
            "id": d["id"],
            "title": d["title"],
            "status": d["status"],
            "cost": d["cost"],
            "recommended_tools": d.get("recommended_tools", []),
        }
        for d in DOMAINS.values()
    ]


def describe_domain(domain_id: str) -> dict:
    if domain_id not in DOMAINS:
        raise ValueError(
            f"Domínio desconhecido: {domain_id}. Use list_domains. "
            f"Disponíveis: {sorted(DOMAINS)}"
        )
    return DOMAINS[domain_id]
