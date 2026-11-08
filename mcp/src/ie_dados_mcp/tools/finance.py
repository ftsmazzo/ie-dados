"""Tools tipadas — prestação de contas (receita/despesa/paga/doador)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from ie_dados_mcp import db
from ie_dados_mcp.limits import (
    ALLOWED_GROUP_BY_DESPESA,
    ALLOWED_GROUP_BY_DOADOR,
    ALLOWED_GROUP_BY_PAGA,
    ALLOWED_GROUP_BY_PAGO_CONTRATADO,
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


def finance_pago_contratado(
    group_by: list[str] | None = None,
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
    """Taxa pago/contratado: soma pagamentos ÷ soma contratada (join por sq_despesa).

    WHEN TO USE: comparar caixa vs compromisso — ex. partido×município em 2020/2024.
    WHEN NOT TO USE: sem escopo; dump de fornecedores; misturar com receita.
    COST: heavy.
    Preferir anos municipais (id_municipio preenchido). Em gerais filtre sg_uf/cd_cargo.
    rate_pago_sobre_contratado > 1 pode ocorrer (pagamentos em mais de uma parcela/ano-contábil).
    """
    group_by = group_by or ["sg_partido"]
    bad = [g for g in group_by if g not in ALLOWED_GROUP_BY_PAGO_CONTRATADO]
    if bad:
        raise ValueError(
            f"group_by inválido: {bad}. Permitidos: {sorted(ALLOWED_GROUP_BY_PAGO_CONTRATADO)}"
        )
    if not (ano_eleicao or id_municipio or sg_uf or sq_candidato):
        raise ValueError(
            "Escopo obrigatório: ano_eleicao e/ou id_municipio e/ou sg_uf e/ou sq_candidato"
        )
    max_rows = clamp_max_rows(max_rows)

    clauses: list[str] = []
    params: list[Any] = []
    if ano_eleicao is not None:
        clauses.append("c.ano_eleicao = %s")
        params.append(ano_eleicao)
    if nr_turno is not None:
        clauses.append("c.nr_turno = %s")
        params.append(nr_turno)
    if sg_uf:
        clauses.append("c.sg_uf = %s")
        params.append(sg_uf.upper())
    if id_municipio:
        clauses.append("c.id_municipio = %s")
        params.append(id_municipio.zfill(7))
    if cd_municipio_tse is not None:
        clauses.append("c.cd_municipio_tse = %s")
        params.append(cd_municipio_tse)
    if cd_cargo is not None:
        clauses.append("c.cd_cargo = %s")
        params.append(cd_cargo)
    if sg_partido:
        clauses.append("c.sg_partido = %s")
        params.append(sg_partido.upper())
    if sq_candidato is not None:
        clauses.append("c.sq_candidato = %s")
        params.append(sq_candidato)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    gb = ", ".join(f"c.{g}" for g in group_by)
    select_g = ", ".join(f"c.{g}" for g in group_by)

    # Agrega paga por (ano, sq_despesa) antes do join para não multiplicar contratada
    base_sql = f"""
        FROM financeiro.despesa_contratada_candidato c
        LEFT JOIN (
            SELECT ano_eleicao, sq_despesa,
                   SUM(vr_pagto_despesa) AS vr_pagto
            FROM financeiro.despesa_paga_candidato
            GROUP BY ano_eleicao, sq_despesa
        ) p
          ON p.ano_eleicao = c.ano_eleicao
         AND p.sq_despesa = c.sq_despesa
        {where}
        GROUP BY {gb}
    """
    est = db.fetch_one(
        f"SELECT COUNT(*) AS n_groups FROM (SELECT 1 {base_sql}) s",
        tuple(params),
    )
    n_groups = int(est["n_groups"]) if est else 0
    server_limit = 5000 if (force_artifact or n_groups > ARTIFACT_THRESHOLD) else max_rows

    sql = f"""
        SELECT {select_g},
               COALESCE(SUM(c.vr_despesa_contratada), 0) AS sum_contratada,
               COALESCE(SUM(p.vr_pagto), 0) AS sum_pago,
               COALESCE(SUM(p.vr_pagto), 0)::float
                 / NULLIF(SUM(c.vr_despesa_contratada), 0) AS rate_pago_sobre_contratado,
               COUNT(*) AS n_despesas_contratadas
        {base_sql}
        ORDER BY sum_contratada DESC NULLS LAST
        LIMIT {int(server_limit)}
    """
    clean = _clean(db.fetch_all(sql, tuple(params)))
    columns = (
        list(clean[0].keys())
        if clean
        else group_by
        + ["sum_contratada", "sum_pago", "rate_pago_sobre_contratado", "n_despesas_contratadas"]
    )
    meta = {
        "group_by": group_by,
        "n_groups_estimated": n_groups,
        "filters": {
            "ano_eleicao": ano_eleicao,
            "id_municipio": id_municipio,
            "cd_cargo": cd_cargo,
            "sg_uf": sg_uf,
            "sg_partido": sg_partido,
        },
        "join": "despesa_paga aggregated by (ano_eleicao, sq_despesa) → contratada",
    }
    if force_artifact or n_groups > ARTIFACT_THRESHOLD or len(clean) > max_rows:
        artifact_id = art.save_artifact(
            kind="finance_pago_contratado",
            title="pago/contratado",
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
