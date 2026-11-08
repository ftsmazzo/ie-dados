"""Limites duros anti-desperdício de tokens."""

from __future__ import annotations

DEFAULT_MAX_ROWS = 50
HARD_CAP_ROWS = 200
ARTIFACT_THRESHOLD = 80  # acima disso, materializa artefato e devolve amostra
SAMPLE_SIZE = 5

ALLOWED_GROUP_BY_VOTACAO = {
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
}

ALLOWED_METRICS_VOTACAO = {
    "sum_votos": "COALESCE(SUM(qt_votos_nominais), 0)",
    "sum_votos_validos": "COALESCE(SUM(qt_votos_nominais_validos), 0)",
    "n_linhas": "COUNT(*)",
}

ALLOWED_GROUP_BY_DETALHE = {
    "ano_eleicao",
    "nr_turno",
    "sg_uf",
    "id_municipio",
    "cd_municipio_tse",
    "nr_zona",
    "cd_cargo",
    "ds_cargo",
}

ALLOWED_METRICS_DETALHE = {
    "sum_aptos": "COALESCE(SUM(qt_aptos), 0)",
    "sum_comparecimento": "COALESCE(SUM(qt_comparecimento), 0)",
    "sum_abstencoes": "COALESCE(SUM(qt_abstencoes), 0)",
    "sum_validos": "COALESCE(SUM(qt_total_votos_validos), 0)",
    "sum_brancos": "COALESCE(SUM(qt_votos_brancos), 0)",
    "sum_nulos": "COALESCE(SUM(qt_votos_nulos), 0)",
    "n_linhas": "COUNT(*)",
    # rates derivados (anti-token: calculados no servidor, não no agente)
    "rate_nulos_sobre_validos": (
        "COALESCE(SUM(qt_votos_nulos), 0)::float"
        " / NULLIF(SUM(qt_total_votos_validos), 0)"
    ),
    "rate_brancos_sobre_validos": (
        "COALESCE(SUM(qt_votos_brancos), 0)::float"
        " / NULLIF(SUM(qt_total_votos_validos), 0)"
    ),
    "rate_abstencao": (
        "COALESCE(SUM(qt_abstencoes), 0)::float / NULLIF(SUM(qt_aptos), 0)"
    ),
    "rate_comparecimento": (
        "COALESCE(SUM(qt_comparecimento), 0)::float / NULLIF(SUM(qt_aptos), 0)"
    ),
}

# Analytics (Fase A)
SERIES_INLINE_MAX = 50
CORRELATE_MIN_POINTS = 5
SERIES_SERVER_MAX = 5000

# Financeiro (Base 3)
_ALLOWED_GROUP_BY_FIN_COMMON = {
    "ano_eleicao",
    "nr_turno",
    "sg_uf",
    "id_municipio",
    "cd_municipio_tse",
    "cd_cargo",
    "ds_cargo",
    "sg_partido",
    "nr_partido",
    "sq_candidato",
}
ALLOWED_GROUP_BY_RECEITA = _ALLOWED_GROUP_BY_FIN_COMMON | {
    "ds_origem_receita",
    "ds_fonte_receita",
}
ALLOWED_GROUP_BY_DESPESA = _ALLOWED_GROUP_BY_FIN_COMMON | {
    "ds_origem_despesa",
}
# alias legado
ALLOWED_GROUP_BY_FINANCEIRO = ALLOWED_GROUP_BY_RECEITA | ALLOWED_GROUP_BY_DESPESA

ALLOWED_METRICS_RECEITA = {
    "sum_receita": "COALESCE(SUM(vr_receita), 0)",
    "n_linhas": "COUNT(*)",
    "n_candidatos": "COUNT(DISTINCT sq_candidato)",
}

ALLOWED_METRICS_DESPESA = {
    "sum_despesa": "COALESCE(SUM(vr_despesa_contratada), 0)",
    "n_linhas": "COUNT(*)",
    "n_candidatos": "COUNT(DISTINCT sq_candidato)",
}

ALLOWED_GROUP_BY_PAGA = {
    "ano_eleicao",
    "nr_turno",
    "sg_uf",
    "ds_origem_despesa",
    "ds_natureza_despesa",
    "ds_fonte_despesa",
    "sq_despesa",
}
ALLOWED_METRICS_PAGA = {
    "sum_pagto": "COALESCE(SUM(vr_pagto_despesa), 0)",
    "n_linhas": "COUNT(*)",
}

ALLOWED_GROUP_BY_DOADOR = {
    "ano_eleicao",
    "nr_turno",
    "sg_uf",
    "tp_doador_originario",
    "ds_cnae_doador_originario",
    "sq_receita",
}
ALLOWED_METRICS_DOADOR = {
    "sum_receita": "COALESCE(SUM(vr_receita), 0)",
    "n_linhas": "COUNT(*)",
    "n_doadores": "COUNT(DISTINCT nr_cpf_cnpj_doador_originario)",
}


def clamp_max_rows(max_rows: int | None) -> int:
    if max_rows is None:
        return DEFAULT_MAX_ROWS
    if max_rows < 1:
        raise ValueError("max_rows deve ser >= 1")
    if max_rows > HARD_CAP_ROWS:
        raise ValueError(
            f"max_rows={max_rows} excede hard cap {HARD_CAP_ROWS}. "
            "Aggrege mais (group_by) ou peça artifact_get em páginas."
        )
    return max_rows
