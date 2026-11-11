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
            "ref.pib_municipio": {
                "description": "PIB municipal IBGE 2010–2023 (mil R$ correntes) + per capita; VABs 2010–2021.",
                "keys": ["id_municipio", "ano"],
                "fields": [
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
            },
            "ref.idhm_municipio": {
                "description": "IDHM Atlas 1991/2000/2010 + dimensões renda/longevidade/educação.",
                "keys": ["id_municipio", "ano"],
                "fields": [
                    "id_municipio",
                    "ano",
                    "idhm",
                    "idhm_renda",
                    "idhm_longevidade",
                    "idhm_educacao",
                    "fonte",
                ],
            },
        },
        "recommended_tools": [
            "resolve_municipio",
            "get_populacao",
            "get_pib",
            "get_idhm",
        ],
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
            "series_build",
            "artifact_get",
        ],
        "derived_metrics_detalhe": [
            "rate_nulos_sobre_validos",
            "rate_brancos_sobre_validos",
            "rate_abstencao",
            "rate_comparecimento",
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
    "analytics": {
        "id": "analytics",
        "title": "Séries temporais e correlações tipadas",
        "status": "pronta",
        "cost": "medium",
        "tables": {
            "virtual.series": {
                "description": (
                    "Séries agregadas por ano a partir de eleitoral.detalhe_munzona "
                    "ou votacao (+ populacao / PIB / IDHM). "
                    "Use series_build → correlate / series_compare. Sem SQL livre."
                ),
                "keys": ["ano_eleicao", "id_municipio"],
                "fields": [
                    "ano_eleicao",
                    "id_municipio",
                    "sum_*",
                    "rate_*",
                    "populacao",
                    "pib_mil",
                    "pib_per_capita",
                    "idhm",
                    "idhm_renda",
                    "idhm_longevidade",
                    "idhm_educacao",
                    "delta",
                    "pct_change",
                    "pearson_r",
                    "spearman_rho",
                ],
            },
        },
        "recommended_tools": [
            "series_build",
            "correlate",
            "series_compare",
            "get_pib",
            "get_idhm",
            "artifact_get",
        ],
        "whitelist_pairs": [
            "detalhe metric ↔ detalhe metric (align_by=ano)",
            "detalhe metric ↔ populacao (align_by=ano, exige id_municipio)",
            "detalhe/votacao metric ↔ pib (align_by=ano com id_municipio; ou municipio+sg_uf)",
            "detalhe/votacao metric ↔ idhm (só align_by=municipio + sg_uf + ano_eleicao)",
        ],
    },
    "financeiro": {
        "id": "financeiro",
        "title": "Prestação de contas — receitas e despesas de candidatos",
        "status": "pronta",
        "cost": "heavy",
        "tables": {
            "financeiro.receita_candidato": {
                "description": (
                    "Receitas de campanha (~5,2M linhas P0). "
                    "Use finance_estimate → finance_aggregate. Ligação: sq_candidato+ano."
                ),
                "keys": ["ano_eleicao", "sq_candidato", "sq_receita"],
                "fields": [
                    "ano_eleicao",
                    "sg_uf",
                    "id_municipio",
                    "cd_cargo",
                    "sq_candidato",
                    "sg_partido",
                    "ds_origem_receita",
                    "ds_fonte_receita",
                    "vr_receita",
                ],
            },
            "financeiro.despesa_contratada_candidato": {
                "description": (
                    "Despesas contratadas (~14M linhas P0). "
                    "finance_aggregate source=despesa."
                ),
                "keys": ["ano_eleicao", "sq_candidato", "sq_despesa"],
                "fields": [
                    "ano_eleicao",
                    "sg_uf",
                    "id_municipio",
                    "cd_cargo",
                    "sq_candidato",
                    "sg_partido",
                    "ds_origem_despesa",
                    "vr_despesa_contratada",
                ],
            },
            "financeiro.despesa_paga_candidato": {
                "description": (
                    "Pagamentos (cash). Liga a contratada via sq_despesa. "
                    "finance_aggregate source=paga. Sem id_municipio no CSV."
                ),
                "keys": ["ano_eleicao", "sq_despesa"],
                "fields": [
                    "ano_eleicao",
                    "sg_uf",
                    "ds_origem_despesa",
                    "ds_natureza_despesa",
                    "vr_pagto_despesa",
                ],
            },
            "financeiro.receita_doador_originario": {
                "description": (
                    "Doador originário. Liga a receita via sq_receita. "
                    "finance_aggregate source=doador."
                ),
                "keys": ["ano_eleicao", "sq_receita"],
                "fields": [
                    "ano_eleicao",
                    "sg_uf",
                    "tp_doador_originario",
                    "nm_doador_originario",
                    "vr_receita",
                ],
            },
        },
        "recommended_tools": [
            "finance_estimate",
            "finance_aggregate",
            "finance_pago_contratado",
            "artifact_get",
        ],
        "years_p0": [2018, 2020, 2022, 2024, 2026],
        "notes": [
            "Municipais (2020/2024): id_municipio preenchido via SG_UE TSE.",
            "Gerais (2018/2022/2026): id_municipio geralmente nulo — filtre UF/cargo/candidato.",
            "source=paga|doador: filtre por ano_eleicao e/ou sg_uf.",
        ],
    },
    "municipios": {
        "id": "municipios",
        "title": "Acervo Municípios (portal institucional)",
        "status": "em_andamento",
        "cost": "medium",
        "tables": {
            "docs.municipio_doc": {
                "description": (
                    "Catálogo de páginas/MD por município e secretaria. "
                    "P0: Ribeirão Preto (id_municipio=3543402)."
                ),
                "keys": ["id_municipio", "path_md"],
                "fields": [
                    "id_doc",
                    "id_municipio",
                    "slug_municipio",
                    "secretaria_slug",
                    "tipo",
                    "titulo",
                    "path_md",
                    "url_fonte",
                    "n_chunks",
                ],
            },
            "docs.municipio_chunk": {
                "description": "Chunks FTS portuguese; use mun_retrieve / mun_search_servico.",
                "keys": ["id_doc", "chunk_ord"],
                "fields": ["id_chunk", "id_doc", "chunk_ord", "secao", "texto"],
            },
        },
        "recommended_tools": [
            "mun_list",
            "mun_list_secretarias",
            "mun_get_secretaria",
            "mun_retrieve",
            "mun_search_servico",
        ],
        "notes": [
            "Sempre informe id_municipio ou slug_municipio.",
            "Ribeirão Preto: slug=ribeirao-preto / 3543402.",
            "Outros municípios: mesmo pipeline scrape→MD→load.",
        ],
    },
    "planos": {
        "id": "planos",
        "title": "Planos de Governo (Acervo RAG)",
        "status": "em_andamento",
        "cost": "medium",
        "tables": {
            "ref.plano_governo": {
                "description": (
                    "Catálogo de PDFs TSE proposta_governo. "
                    "Todos candidatos executivos; flag eleito. "
                    "Presidente atual = eleito 2026 (cd_cargo=1)."
                ),
                "keys": ["ano_eleicao", "sq_candidato", "arquivo_nome"],
                "fields": [
                    "id_plano",
                    "ano_eleicao",
                    "cd_cargo",
                    "ds_cargo",
                    "sg_uf",
                    "id_municipio",
                    "sq_candidato",
                    "nm_candidato",
                    "sg_partido",
                    "eleito",
                    "arquivo_nome",
                    "n_chunks",
                ],
            },
            "docs.plano_chunk": {
                "description": "Chunks FTS (portuguese) do acervo; use plano_retrieve.",
                "keys": ["id_plano", "chunk_ord"],
                "fields": ["id_chunk", "id_plano", "chunk_ord", "secao", "texto"],
            },
        },
        "recommended_tools": [
            "plano_search_meta",
            "plano_retrieve",
            "plano_compare_tema",
            "plano_seed_ideia",
            "get_pib",
            "get_idhm",
        ],
        "years_p0": [2018, 2020, 2022, 2024, 2026],
        "notes": [
            "cd_cargo: 1 Presidente, 3 Governador, 11 Prefeito.",
            "eleito=true marca quem venceu; mandato presidencial atual = 2026.",
            "Municipais: ZIPs por UF (grandes). Gerais BR são leves.",
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
