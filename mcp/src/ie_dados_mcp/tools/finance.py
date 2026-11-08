"""Tools tipadas — prestação de contas (receitas / despesas contratadas)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from ie_dados_mcp import db
from ie_dados_mcp.limits import (
    ALLOWED_GROUP_BY_DESPESA,
    ALLOWED_GROUP_BY_RECEITA,
    ALLOWED_METRICS_DESPESA,
    ALLOWED_METRICS_RECEITA,
    ARTIFACT_THRESHOLD,
    SAMPLE_SIZE,
    clamp_max_rows,
)
from ie_dados_mcp.tools import artifacts as art

Source = Literal["receita", "despesa"]


def _validate(group_by: list[str], metrics: list[str], source: Source):
    if not group_by:
        raise ValueError("group_by obrigatório. Ex.: ['ano_eleicao','sg_partido']")
    if not metrics:
        raise ValueError("metrics obrigatório. Ex.: ['sum_receita'] ou ['sum_despesa']")
    allowed_g = ALLOWED_GROUP_BY_RECEITA if source == "receita" else ALLOWED_GROUP_BY_DESPESA
    allowed_m = ALLOWED_METRICS_RECEITA if source == "receita" else ALLOWED_METRICS_DESPESA
    bad_g = [g for g in group_by if g not in allowed_g]
    bad_m = [m for m in metrics if m not in allowed_m]
    if bad_g:
        raise ValueError(f"group_by inválido: {bad_g}. Permitidos: {sorted(allowed_g)}")
    if bad_m:
        raise ValueError(f"metrics inválidas: {bad_m}. Permitidas: {sorted(allowed_m)}")
    return group_by, metrics, allowed_m


def _filters_sql(
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
    clauses: list[str] = []
    params: list[Any] = []
    if ano_eleicao is not None:
        clauses.append("ano_eleicao = %s")
        params.append(ano_eleicao)
    if nr_turno is not None:
        clauses.append("nr_turno = %s")
        params.append(nr_turno)
    if sg_uf:
        clauses.append("sg_uf = %s")
        params.append(sg_uf.upper())
    if id_municipio:
        clauses.append("id_municipio = %s")
        params.append(id_municipio.zfill(7))
    if cd_municipio_tse is not None:
        clauses.append("cd_municipio_tse = %s")
        params.append(cd_municipio_tse)
    if cd_cargo is not None:
        clauses.append("cd_cargo = %s")
        params.append(cd_cargo)
    if sg_partido:
        clauses.append("sg_partido = %s")
        params.append(sg_partido.upper())
    if sq_candidato is not None:
        clauses.append("sq_candidato = %s")
        params.append(sq_candidato)
    if require_scope and not (ano_eleicao or id_municipio or sg_uf or sq_candidato):
        raise ValueError(
            "Filtro de escopo obrigatório: ano_eleicao e/ou id_municipio e/ou sg_uf "
            "e/ou sq_candidato."
        )
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _table(source: Source) -> str:
    return (
        "financeiro.receita_candidato"
        if source == "receita"
        else "financeiro.despesa_contratada_candidato"
    )


def _build_sql(
    source: Source,
    group_by: list[str],
    metrics: list[str],
    metric_map: dict[str, str],
    where: str,
    limit: int | None,
    count_only: bool,
) -> str:
    table = _table(source)
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
    """Estima quantos grupos finance_aggregate geraria — sem devolver linhas.

    WHEN TO USE: antes de agregações amplas de receita/despesa.
    WHEN NOT TO USE: consulta já estreita (1 município + 1 ano + 1 cargo).
    COST: cheap.
    """
    if source not in ("receita", "despesa"):
        raise ValueError("source: receita | despesa")
    group_by = group_by or ["ano_eleicao"]
    metrics = metrics or (["sum_receita"] if source == "receita" else ["sum_despesa"])
    group_by, metrics, metric_map = _validate(group_by, metrics, source)
    where, params = _filters_sql(
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
    """Agrega receitas ou despesas contratadas. group_by + metrics obrigatórios.

    WHEN TO USE: cruzar dinheiro × partido/cargo/município após finance_estimate.
    WHEN NOT TO USE: dump de doadores/fornecedores linha a linha.
    COST: heavy.
    Nota: em eleições gerais id_municipio costuma ser nulo (UE=UF); use municipais
    (2020/2024) ou filtre por sq_candidato / sg_uf / cd_cargo.
    """
    if source not in ("receita", "despesa"):
        raise ValueError("source: receita | despesa")
    group_by = group_by or ["sg_partido"]
    metrics = metrics or (["sum_receita"] if source == "receita" else ["sum_despesa"])
    group_by, metrics, metric_map = _validate(group_by, metrics, source)
    max_rows = clamp_max_rows(max_rows)
    where, params = _filters_sql(
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
    est_sql = _build_sql(source, group_by, metrics, metric_map, where, None, True)
    est = db.fetch_one(est_sql, tuple(params))
    n_groups = int(est["n_groups"]) if est else 0
    server_limit = 5000 if (force_artifact or n_groups > ARTIFACT_THRESHOLD) else max_rows
    sql = _build_sql(source, group_by, metrics, metric_map, where, server_limit, False)
    clean = _clean(db.fetch_all(sql, tuple(params)))
    columns = list(clean[0].keys()) if clean else group_by + metrics
    meta = {
        "source": source,
        "group_by": group_by,
        "metrics": metrics,
        "n_groups_estimated": n_groups,
        "filters": {
            "ano_eleicao": ano_eleicao,
            "id_municipio": id_municipio,
            "cd_cargo": cd_cargo,
            "sg_uf": sg_uf,
            "sg_partido": sg_partido,
            "sq_candidato": sq_candidato,
        },
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
