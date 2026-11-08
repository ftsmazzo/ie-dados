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
