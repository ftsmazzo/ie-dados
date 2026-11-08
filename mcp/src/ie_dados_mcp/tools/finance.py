"""Tools tipadas — prestação de contas (receita/despesa/paga/doador)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from ie_dados_mcp import db
from ie_dados_mcp.limits import (
    ALLOWED_GROUP_BY_DESPESA,
    ALLOWED_GROUP_BY_DOADOR,
    ALLOWED_GROUP_BY_PAGA,
    ALLOWED_GROUP_BY_RECEITA,
    ALLOWED_METRICS_DESPESA,
    ALLOWED_METRICS_DOADOR,
    ALLOWED_METRICS_PAGA,
    ALLOWED_METRICS_RECEITA,
    ARTIFACT_THRESHOLD,
    SAMPLE_SIZE,
    clamp_max_rows,
)
from ie_dados_mcp.tools import artifacts as art

Source = Literal["receita", "despesa", "paga", "doador"]

_TABLE = {
    "receita": "financeiro.receita_candidato",
    "despesa": "financeiro.despesa_contratada_candidato",
    "paga": "financeiro.despesa_paga_candidato",
    "doador": "financeiro.receita_doador_originario",
}
_GROUP = {
    "receita": ALLOWED_GROUP_BY_RECEITA,
    "despesa": ALLOWED_GROUP_BY_DESPESA,
    "paga": ALLOWED_GROUP_BY_PAGA,
    "doador": ALLOWED_GROUP_BY_DOADOR,
}
_METRICS = {
    "receita": ALLOWED_METRICS_RECEITA,
    "despesa": ALLOWED_METRICS_DESPESA,
    "paga": ALLOWED_METRICS_PAGA,
    "doador": ALLOWED_METRICS_DOADOR,
}
# colunas de filtro disponíveis por source
_FILTER_COLS = {
    "receita": {
        "ano_eleicao",
        "nr_turno",
        "sg_uf",
        "id_municipio",
        "cd_municipio_tse",
        "cd_cargo",
        "sg_partido",
        "sq_candidato",
    },
    "despesa": {
        "ano_eleicao",
        "nr_turno",
        "sg_uf",
        "id_municipio",
        "cd_municipio_tse",
        "cd_cargo",
        "sg_partido",
        "sq_candidato",
    },
    "paga": {"ano_eleicao", "nr_turno", "sg_uf"},
    "doador": {"ano_eleicao", "nr_turno", "sg_uf"},
}


def _validate(group_by: list[str], metrics: list[str], source: Source):
    if not group_by:
        raise ValueError("group_by obrigatório")
    if not metrics:
        raise ValueError("metrics obrigatório")
    allowed_g = _GROUP[source]
    allowed_m = _METRICS[source]
    bad_g = [g for g in group_by if g not in allowed_g]
    bad_m = [m for m in metrics if m not in allowed_m]
    if bad_g:
        raise ValueError(f"group_by inválido: {bad_g}. Permitidos: {sorted(allowed_g)}")
    if bad_m:
        raise ValueError(f"metrics inválidas: {bad_m}. Permitidas: {sorted(allowed_m)}")
    return group_by, metrics, allowed_m


def _filters_sql(
    source: Source,
    *,
    ano_eleicao: int | None,
    nr_turno: int | None,
    sg_uf: str | None,
    id_municipio: str | None,
    cd_municipio_tse: int | None,
    cd_cargo: int | None,
    sg_partido: str | None,
    sq_candidato: int | None,
    require_scope: bool,
) -> tuple[str, list[Any]]:
    allowed = _FILTER_COLS[source]
    wanted = {
        "ano_eleicao": ano_eleicao,
        "nr_turno": nr_turno,
        "sg_uf": sg_uf.upper() if sg_uf else None,
        "id_municipio": id_municipio.zfill(7) if id_municipio else None,
        "cd_municipio_tse": cd_municipio_tse,
        "cd_cargo": cd_cargo,
        "sg_partido": sg_partido.upper() if sg_partido else None,
        "sq_candidato": sq_candidato,
    }
    for k, v in list(wanted.items()):
        if v is None:
            continue
        if k not in allowed:
            raise ValueError(
                f"Filtro '{k}' não existe em source={source}. "
                f"Disponíveis: {sorted(allowed)}"
            )

    clauses: list[str] = []
    params: list[Any] = []
    for col, val in wanted.items():
        if val is None or col not in allowed:
            continue
        clauses.append(f"{col} = %s")
        params.append(val)

    scoped = any(
        wanted[c] is not None
        for c in ("ano_eleicao", "id_municipio", "sg_uf", "sq_candidato")
        if c in allowed or c in ("ano_eleicao", "sg_uf")
    )
    # paga/doador: escopo = ano e/ou uf
    if source in ("paga", "doador"):
        scoped = ano_eleicao is not None or bool(sg_uf)
    if require_scope and not scoped:
        raise ValueError(
            "Filtro de escopo obrigatório: ano_eleicao e/ou sg_uf "
            "(e id_municipio/sq_candidato quando a source tiver)."
        )
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _build_sql(
    source: Source,
    group_by: list[str],
    metrics: list[str],
    metric_map: dict[str, str],
    where: str,
    limit: int | None,
    count_only: bool,
) -> str:
    table = _TABLE[source]
    if count_only:
        return (
            f"SELECT COUNT(*) AS n_groups FROM ("
            f"SELECT 1 FROM {table}{where} GROUP BY {', '.join(group_by)}) s"
        )
    select_parts = list(group_by) + [f"{metric_map[m]} AS {m}" for m in metrics]
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {table}{where} "
        f"GROUP BY {', '.join(group_by)} "
        f"ORDER BY {metrics[0]} DESC NULLS LAST"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return sql


def _clean(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        item = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                item[k] = int(v) if v == v.to_integral_value() else float(v)
            else:
                item[k] = v
        out.append(item)
    return out


def _default_metrics(source: Source) -> list[str]:
    return {
        "receita": ["sum_receita"],
        "despesa": ["sum_despesa"],
        "paga": ["sum_pagto"],
        "doador": ["sum_receita"],
    }[source]


def finance_estimate(
    source: Source = "receita",
    group_by: list[str] | None = None,
    metrics: list[str] | None = None,
    ano_eleicao: int | None = None,
    nr_turno: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    cd_cargo: int | None = None,
    sg_partido: str | None = None,
    sq_candidato: int | None = None,
) -> dict:
    """Estima grupos de finance_aggregate — sem devolver linhas.

    WHEN TO USE: antes de agregações amplas.
    source: receita | despesa | paga | doador
    COST: cheap.
    """
    if source not in _TABLE:
        raise ValueError("source: receita | despesa | paga | doador")
    group_by = group_by or ["ano_eleicao"]
    metrics = metrics or _default_metrics(source)
    group_by, metrics, metric_map = _validate(group_by, metrics, source)
    where, params = _filters_sql(
        source,
        ano_eleicao=ano_eleicao,
        nr_turno=nr_turno,
        sg_uf=sg_uf,
        id_municipio=id_municipio,
        cd_municipio_tse=cd_municipio_tse,
        cd_cargo=cd_cargo,
        sg_partido=sg_partido,
        sq_candidato=sq_candidato,
        require_scope=True,
    )
    sql = _build_sql(source, group_by, metrics, metric_map, where, None, True)
    row = db.fetch_one(sql, tuple(params))
    n_groups = int(row["n_groups"]) if row else 0
    return {
        "source": source,
        "n_groups": n_groups,
        "group_by": group_by,
        "metrics": metrics,
        "recommendation": (
            "safe_inline" if n_groups <= ARTIFACT_THRESHOLD else "use_artifact_or_narrow_filters"
        ),
        "cost": "cheap",
    }


def finance_aggregate(
    source: Source = "receita",
    group_by: list[str] | None = None,
    metrics: list[str] | None = None,
    ano_eleicao: int | None = None,
    nr_turno: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    cd_cargo: int | None = None,
    sg_partido: str | None = None,
    sq_candidato: int | None = None,
    max_rows: int | None = 50,
    force_artifact: bool = False,
) -> dict:
    """Agrega prestação tipada. group_by + metrics obrigatórios.

    WHEN TO USE: dinheiro por partido/origem/UF; paga=cash; doador=origem final.
    WHEN NOT TO USE: dump de CPF/CNPJ linha a linha.
    COST: heavy.
    """
    if source not in _TABLE:
        raise ValueError("source: receita | despesa | paga | doador")
    group_by = group_by or (["sg_partido"] if source in ("receita", "despesa") else ["sg_uf"])
    metrics = metrics or _default_metrics(source)
    group_by, metrics, metric_map = _validate(group_by, metrics, source)
    max_rows = clamp_max_rows(max_rows)
    where, params = _filters_sql(
        source,
        ano_eleicao=ano_eleicao,
        nr_turno=nr_turno,
        sg_uf=sg_uf,
        id_municipio=id_municipio,
        cd_municipio_tse=cd_municipio_tse,
        cd_cargo=cd_cargo,
        sg_partido=sg_partido,
        sq_candidato=sq_candidato,
        require_scope=True,
    )
    est = db.fetch_one(
        _build_sql(source, group_by, metrics, metric_map, where, None, True),
        tuple(params),
    )
    n_groups = int(est["n_groups"]) if est else 0
    server_limit = 5000 if (force_artifact or n_groups > ARTIFACT_THRESHOLD) else max_rows
    clean = _clean(
        db.fetch_all(
            _build_sql(source, group_by, metrics, metric_map, where, server_limit, False),
            tuple(params),
        )
    )
    columns = list(clean[0].keys()) if clean else group_by + metrics
    meta = {
        "source": source,
        "group_by": group_by,
        "metrics": metrics,
        "n_groups_estimated": n_groups,
    }
    if force_artifact or n_groups > ARTIFACT_THRESHOLD or len(clean) > max_rows:
        artifact_id = art.save_artifact(
            kind="finance_aggregate",
            title=f"{source} aggregate",
            columns=columns,
            rows=clean,
            meta=meta,
        )
        return {
            "mode": "artifact",
            "artifact_id": artifact_id,
            "n_rows": len(clean),
            "n_groups_estimated": n_groups,
            "columns": columns,
            "sample": clean[:SAMPLE_SIZE],
            "cost": "heavy",
        }
    return {
        "mode": "inline",
        "n_rows": len(clean),
        "n_groups_estimated": n_groups,
        "columns": columns,
        "rows": clean,
        "meta": meta,
        "cost": "heavy",
    }
