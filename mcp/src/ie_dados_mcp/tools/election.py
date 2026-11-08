from __future__ import annotations

import json
from typing import Any, Literal

from ie_dados_mcp import db
from ie_dados_mcp.limits import (
    ALLOWED_GROUP_BY_DETALHE,
    ALLOWED_GROUP_BY_VOTACAO,
    ALLOWED_METRICS_DETALHE,
    ALLOWED_METRICS_VOTACAO,
    ARTIFACT_THRESHOLD,
    SAMPLE_SIZE,
    clamp_max_rows,
)
from ie_dados_mcp.tools import artifacts as art

Source = Literal["votacao", "detalhe"]


def _validate_lists(
    group_by: list[str],
    metrics: list[str],
    source: Source,
) -> tuple[list[str], list[str], dict[str, str], dict[str, str]]:
    if not group_by:
        raise ValueError(
            "group_by é obrigatório. Ex.: ['ano_eleicao','sg_partido'] "
            "— nunca peça o fato cru de votacao_candidato_munzona."
        )
    if not metrics:
        raise ValueError("metrics é obrigatório. Ex.: ['sum_votos','n_linhas']")

    allowed_g = ALLOWED_GROUP_BY_VOTACAO if source == "votacao" else ALLOWED_GROUP_BY_DETALHE
    allowed_m = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE

    bad_g = [g for g in group_by if g not in allowed_g]
    bad_m = [m for m in metrics if m not in allowed_m]
    if bad_g:
        raise ValueError(f"group_by inválido: {bad_g}. Permitidos: {sorted(allowed_g)}")
    if bad_m:
        raise ValueError(f"metrics inválidas: {bad_m}. Permitidas: {sorted(allowed_m)}")
    return group_by, metrics, allowed_g, allowed_m


def _filters_sql(
    *,
    ano_eleicao: int | None,
    nr_turno: int | None,
    sg_uf: str | None,
    id_municipio: str | None,
    cd_municipio_tse: int | None,
    nr_zona: int | None,
    cd_cargo: int | None,
    sg_partido: str | None,
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
    if nr_zona is not None:
        clauses.append("nr_zona = %s")
        params.append(nr_zona)
    if cd_cargo is not None:
        clauses.append("cd_cargo = %s")
        params.append(cd_cargo)
    if sg_partido:
        clauses.append("sg_partido = %s")
        params.append(sg_partido.upper())

    # Escopo mínimo para heavy: ano OU município OU UF
    if require_scope and not (ano_eleicao or id_municipio or sg_uf):
        raise ValueError(
            "Filtro de escopo obrigatório: informe ano_eleicao e/ou id_municipio e/ou sg_uf "
            "para evitar varredura nacional sem recorte."
        )

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _build_agg_sql(
    source: Source,
    group_by: list[str],
    metrics: list[str],
    where: str,
    limit: int | None,
    count_only: bool,
) -> str:
    table = (
        "eleitoral.votacao_candidato_munzona"
        if source == "votacao"
        else "eleitoral.detalhe_munzona"
    )
    metric_map = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE

    if count_only:
        return f"SELECT COUNT(*) AS n_groups FROM (SELECT 1 FROM {table}{where} GROUP BY {', '.join(group_by)}) s"

    select_parts = list(group_by) + [
        f"{metric_map[m]} AS {m}" for m in metrics
    ]
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {table}{where} "
        f"GROUP BY {', '.join(group_by)} "
        f"ORDER BY {metrics[0]} DESC"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return sql


def election_estimate(
    source: Source = "votacao",
    group_by: list[str] | None = None,
    metrics: list[str] | None = None,
    ano_eleicao: int | None = None,
    nr_turno: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    nr_zona: int | None = None,
    cd_cargo: int | None = None,
    sg_partido: str | None = None,
) -> dict:
    """Estima quantos grupos a agregação geraria — SEM devolver as linhas.

    WHEN TO USE: sempre antes de election_aggregate em consultas amplas.
    WHEN NOT TO USE: consultas já muito estreitas (1 município + 1 ano + 1 cargo).
    COST: cheap (relativo ao aggregate).
    """
    group_by = group_by or ["ano_eleicao"]
    metrics = metrics or (["sum_votos"] if source == "votacao" else ["sum_comparecimento"])
    group_by, metrics, _, _ = _validate_lists(group_by, metrics, source)
    where, params = _filters_sql(
        ano_eleicao=ano_eleicao,
        nr_turno=nr_turno,
        sg_uf=sg_uf,
        id_municipio=id_municipio,
        cd_municipio_tse=cd_municipio_tse,
        nr_zona=nr_zona,
        cd_cargo=cd_cargo,
        sg_partido=sg_partido,
        require_scope=True,
    )
    sql = _build_agg_sql(source, group_by, metrics, where, limit=None, count_only=True)
    row = db.fetch_one(sql, tuple(params))
    n_groups = int(row["n_groups"]) if row else 0
    return {
        "source": source,
        "n_groups": n_groups,
        "group_by": group_by,
        "metrics": metrics,
        "recommendation": (
            "safe_inline"
            if n_groups <= ARTIFACT_THRESHOLD
            else "use_artifact_or_narrow_filters"
        ),
        "hint": (
            "Chame election_aggregate com os mesmos filtros."
            if n_groups <= ARTIFACT_THRESHOLD
            else (
                f"{n_groups} grupos > limiar {ARTIFACT_THRESHOLD}. "
                "Aperte filtros ou aceite artifact_id na resposta do aggregate."
            )
        ),
    }


def election_aggregate(
    source: Source = "votacao",
    group_by: list[str] | None = None,
    metrics: list[str] | None = None,
    ano_eleicao: int | None = None,
    nr_turno: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    nr_zona: int | None = None,
    cd_cargo: int | None = None,
    sg_partido: str | None = None,
    max_rows: int | None = 50,
    force_artifact: bool = False,
) -> dict:
    """Agrega votos ou comparecimento. group_by + metrics obrigatórios.

    WHEN TO USE: após election_estimate (ou consulta estreita já conhecida).
    WHEN NOT TO USE: nunca sem group_by; nunca para dump de candidatos brutos.
    COST: heavy.
    RETURNS: rows inline se pequeno; senão {artifact_id, n_rows, sample} sem o corpo completo.
    """
    group_by = group_by or ["sg_partido"]
    metrics = metrics or (["sum_votos"] if source == "votacao" else ["sum_comparecimento"])
    group_by, metrics, _, _ = _validate_lists(group_by, metrics, source)
    max_rows = clamp_max_rows(max_rows)

    where, params = _filters_sql(
        ano_eleicao=ano_eleicao,
        nr_turno=nr_turno,
        sg_uf=sg_uf,
        id_municipio=id_municipio,
        cd_municipio_tse=cd_municipio_tse,
        nr_zona=nr_zona,
        cd_cargo=cd_cargo,
        sg_partido=sg_partido,
        require_scope=True,
    )

    # estimate groups first (cheap)
    est_sql = _build_agg_sql(source, group_by, metrics, where, limit=None, count_only=True)
    est = db.fetch_one(est_sql, tuple(params))
    n_groups = int(est["n_groups"]) if est else 0

    # fetch capped
    fetch_limit = max(max_rows, ARTIFACT_THRESHOLD + 1) if (force_artifact or n_groups > ARTIFACT_THRESHOLD) else max_rows
    # hard safety: never pull more than HARD via clamp already on max_rows for inline;
    # for artifact path allow up to 5000 server-side then store
    server_limit = 5000 if (force_artifact or n_groups > ARTIFACT_THRESHOLD) else max_rows
    sql = _build_agg_sql(source, group_by, metrics, where, limit=server_limit, count_only=False)
    from decimal import Decimal

    rows = db.fetch_all(sql, tuple(params))
    clean = []
    for r in rows:
        item = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                item[k] = int(v) if v == v.to_integral_value() else float(v)
            else:
                item[k] = v
        clean.append(item)

    columns = list(clean[0].keys()) if clean else group_by + metrics
    meta = {
        "source": source,
        "group_by": group_by,
        "metrics": metrics,
        "n_groups_estimated": n_groups,
        "filters": {
            "ano_eleicao": ano_eleicao,
            "nr_turno": nr_turno,
            "sg_uf": sg_uf,
            "id_municipio": id_municipio,
            "cd_municipio_tse": cd_municipio_tse,
            "nr_zona": nr_zona,
            "cd_cargo": cd_cargo,
            "sg_partido": sg_partido,
        },
    }

    if force_artifact or n_groups > ARTIFACT_THRESHOLD or len(clean) > max_rows:
        artifact_id = art.save_artifact(
            kind="election_aggregate",
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
            "hint": "Resultado grande guardado no servidor. Use artifact_get para páginas/resumo.",
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
