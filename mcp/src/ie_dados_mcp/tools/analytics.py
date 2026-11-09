"""Camada analytics tipada — séries, correlação e comparação YoY.

Reusa filtros/métricas de election. Sem SQL livre. Resultados grandes → artifact.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Literal

from ie_dados_mcp import db
from ie_dados_mcp.limits import (
    ALLOWED_METRICS_DETALHE,
    ALLOWED_METRICS_VOTACAO,
    CORRELATE_MIN_POINTS,
    SAMPLE_SIZE,
    SERIES_INLINE_MAX,
    SERIES_SERVER_MAX,
    clamp_max_rows,
)
from ie_dados_mcp.tools import artifacts as art
from ie_dados_mcp.tools.election import (
    Source,
    _filters_sql,
    _validate_lists,
)

SeriesY = Literal["metric", "populacao", "pib", "idhm"]
AlignBy = Literal["ano", "municipio"]

PIB_METRICS = {
    "pib_mil": "pib_mil",
    "pib_per_capita": "pib_per_capita",
}
IDHM_METRICS = {
    "idhm": "idhm",
    "idhm_renda": "idhm_renda",
    "idhm_longevidade": "idhm_longevidade",
    "idhm_educacao": "idhm_educacao",
}
IDHM_ANOS = (1991, 2000, 2010)
PIB_ANO_MIN, PIB_ANO_MAX = 2010, 2023


def _clean_rows(rows: list[dict]) -> list[dict]:
    clean: list[dict] = []
    for r in rows:
        item: dict[str, Any] = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                item[k] = int(v) if v == v.to_integral_value() else float(v)
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                item[k] = None
            else:
                item[k] = v
        clean.append(item)
    return clean


def _maybe_artifact(
    *,
    kind: str,
    title: str,
    rows: list[dict],
    meta: dict,
    max_rows: int,
    force_artifact: bool = False,
) -> dict:
    columns = list(rows[0].keys()) if rows else list(meta.get("columns") or [])
    if force_artifact or len(rows) > max_rows:
        artifact_id = art.save_artifact(
            kind=kind,
            title=title,
            columns=columns,
            rows=rows,
            meta=meta,
        )
        return {
            "mode": "artifact",
            "artifact_id": artifact_id,
            "n_rows": len(rows),
            "columns": columns,
            "sample": rows[:SAMPLE_SIZE],
            "meta": meta,
            "hint": "Série grande no servidor. Use artifact_get para páginas.",
            "cost": "medium",
        }
    return {
        "mode": "inline",
        "n_rows": len(rows),
        "columns": columns,
        "rows": rows,
        "meta": meta,
        "cost": "medium",
    }


def _fetch_metric_series(
    *,
    source: Source,
    metric: str,
    group_by: list[str],
    ano_eleicao: int | None,
    nr_turno: int | None,
    sg_uf: str | None,
    id_municipio: str | None,
    cd_municipio_tse: int | None,
    nr_zona: int | None,
    cd_cargo: int | None,
    sg_partido: str | None,
    limit: int,
) -> list[dict]:
    group_by, metrics, _, _ = _validate_lists(group_by, [metric], source)
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
    # time series: order by first group key ASC when it is ano_eleicao
    table = (
        "eleitoral.votacao_candidato_munzona"
        if source == "votacao"
        else "eleitoral.detalhe_munzona"
    )
    metric_map = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE
    select_parts = list(group_by) + [f"{metric_map[metrics[0]]} AS {metrics[0]}"]
    order = (
        "ano_eleicao ASC NULLS LAST"
        if "ano_eleicao" in group_by
        else f"{metrics[0]} DESC NULLS LAST"
    )
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {table}{where} "
        f"GROUP BY {', '.join(group_by)} "
        f"ORDER BY {order} "
        f"LIMIT {int(limit)}"
    )
    return _clean_rows(db.fetch_all(sql, tuple(params)))


def _fetch_populacao_series(
    *,
    id_municipio: str,
    anos: list[int] | None = None,
) -> list[dict]:
    mid = id_municipio.zfill(7)
    if anos:
        rows = db.fetch_all(
            """
            SELECT ano AS ano_eleicao, populacao
            FROM ref.populacao_municipio
            WHERE id_municipio = %s AND ano = ANY(%s)
            ORDER BY ano
            """,
            (mid, anos),
        )
    else:
        rows = db.fetch_all(
            """
            SELECT ano AS ano_eleicao, populacao
            FROM ref.populacao_municipio
            WHERE id_municipio = %s
            ORDER BY ano
            """,
            (mid,),
        )
    return _clean_rows(rows)


def _map_idhm_ano(ano: int) -> int:
    return min(IDHM_ANOS, key=lambda y: abs(y - ano))


def _clamp_pib_ano(ano: int) -> int:
    return max(PIB_ANO_MIN, min(PIB_ANO_MAX, ano))


def _fetch_pib_series(
    *,
    id_municipio: str,
    metric_y: str,
    anos: list[int] | None = None,
) -> list[dict]:
    if metric_y not in PIB_METRICS:
        raise ValueError(f"metric_y PIB inválida. Permitidas: {sorted(PIB_METRICS)}")
    col = PIB_METRICS[metric_y]
    mid = id_municipio.zfill(7)
    if anos:
        rows = db.fetch_all(
            f"""
            SELECT ano AS ano_eleicao, {col} AS value
            FROM ref.pib_municipio
            WHERE id_municipio = %s AND ano = ANY(%s)
            ORDER BY ano
            """,
            (mid, anos),
        )
    else:
        rows = db.fetch_all(
            f"""
            SELECT ano AS ano_eleicao, {col} AS value
            FROM ref.pib_municipio
            WHERE id_municipio = %s
            ORDER BY ano
            """,
            (mid,),
        )
    return _clean_rows(rows)


def _fetch_idhm_series(
    *,
    id_municipio: str,
    metric_y: str,
    anos: list[int] | None = None,
) -> list[dict]:
    if metric_y not in IDHM_METRICS:
        raise ValueError(f"metric_y IDHM inválida. Permitidas: {sorted(IDHM_METRICS)}")
    col = IDHM_METRICS[metric_y]
    mid = id_municipio.zfill(7)
    if anos:
        mapped = sorted({_map_idhm_ano(a) for a in anos})
        rows = db.fetch_all(
            f"""
            SELECT ano AS ano_eleicao, {col} AS value
            FROM ref.idhm_municipio
            WHERE id_municipio = %s AND ano = ANY(%s)
            ORDER BY ano
            """,
            (mid, mapped),
        )
    else:
        rows = db.fetch_all(
            f"""
            SELECT ano AS ano_eleicao, {col} AS value
            FROM ref.idhm_municipio
            WHERE id_municipio = %s
            ORDER BY ano
            """,
            (mid,),
        )
    return _clean_rows(rows)


def _fetch_metric_by_municipio(
    *,
    source: Source,
    metric: str,
    ano_eleicao: int,
    nr_turno: int | None,
    sg_uf: str,
    cd_cargo: int | None,
    sg_partido: str | None,
    limit: int,
) -> list[dict]:
    group_by, metrics, _, _ = _validate_lists(["id_municipio"], [metric], source)
    where, params = _filters_sql(
        ano_eleicao=ano_eleicao,
        nr_turno=nr_turno,
        sg_uf=sg_uf,
        id_municipio=None,
        cd_municipio_tse=None,
        nr_zona=None,
        cd_cargo=cd_cargo,
        sg_partido=sg_partido,
        require_scope=True,
    )
    table = (
        "eleitoral.votacao_candidato_munzona"
        if source == "votacao"
        else "eleitoral.detalhe_munzona"
    )
    metric_map = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE
    sql = (
        f"SELECT id_municipio, {metric_map[metrics[0]]} AS {metrics[0]} "
        f"FROM {table}{where} "
        f"GROUP BY id_municipio "
        f"ORDER BY {metrics[0]} DESC NULLS LAST "
        f"LIMIT {int(limit)}"
    )
    return _clean_rows(db.fetch_all(sql, tuple(params)))


def _fetch_pib_by_municipio(
    *,
    metric_y: str,
    ano: int,
    sg_uf: str,
    limit: int,
) -> tuple[list[dict], int]:
    if metric_y not in PIB_METRICS:
        raise ValueError(f"metric_y PIB inválida. Permitidas: {sorted(PIB_METRICS)}")
    col = PIB_METRICS[metric_y]
    ano_pib = _clamp_pib_ano(ano)
    rows = db.fetch_all(
        f"""
        SELECT p.id_municipio, p.{col} AS value
        FROM ref.pib_municipio p
        JOIN ref.municipio m ON m.id_municipio = p.id_municipio
        WHERE p.ano = %s AND m.sigla_uf = %s AND p.{col} IS NOT NULL
        ORDER BY p.{col} DESC
        LIMIT %s
        """,
        (ano_pib, sg_uf.upper(), limit),
    )
    return _clean_rows(rows), ano_pib


def _fetch_idhm_by_municipio(
    *,
    metric_y: str,
    ano: int,
    sg_uf: str,
    limit: int,
) -> tuple[list[dict], int]:
    if metric_y not in IDHM_METRICS:
        raise ValueError(f"metric_y IDHM inválida. Permitidas: {sorted(IDHM_METRICS)}")
    col = IDHM_METRICS[metric_y]
    ano_idhm = _map_idhm_ano(ano)
    rows = db.fetch_all(
        f"""
        SELECT i.id_municipio, i.{col} AS value
        FROM ref.idhm_municipio i
        JOIN ref.municipio m ON m.id_municipio = i.id_municipio
        WHERE i.ano = %s AND m.sigla_uf = %s AND i.{col} IS NOT NULL
        ORDER BY i.{col} DESC
        LIMIT %s
        """,
        (ano_idhm, sg_uf.upper(), limit),
    )
    return _clean_rows(rows), ano_idhm


def series_build(
    source: Source = "detalhe",
    metrics: list[str] | None = None,
    group_by: list[str] | None = None,
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
    """Materializa série temporal agregada (ex.: nulos/válidos por ano).

    WHEN TO USE: painéis ao longo dos anos; antes de correlate.
    WHEN NOT TO USE: um único ano sem série — use election_aggregate.
    COST: medium.
    """
    if source not in ("votacao", "detalhe"):
        raise ValueError("source deve ser 'votacao' ou 'detalhe'")
    group_by = group_by or ["ano_eleicao"]
    if "ano_eleicao" not in group_by:
        raise ValueError(
            "series_build exige 'ano_eleicao' em group_by (série temporal tipada)."
        )
    default_m = (
        ["sum_nulos", "sum_validos", "rate_nulos_sobre_validos"]
        if source == "detalhe"
        else ["sum_votos"]
    )
    metrics = metrics or default_m
    if not metrics:
        raise ValueError("metrics obrigatório")
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
    table = (
        "eleitoral.votacao_candidato_munzona"
        if source == "votacao"
        else "eleitoral.detalhe_munzona"
    )
    metric_map = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE
    select_parts = list(group_by) + [f"{metric_map[m]} AS {m}" for m in metrics]
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {table}{where} "
        f"GROUP BY {', '.join(group_by)} "
        f"ORDER BY ano_eleicao ASC NULLS LAST "
        f"LIMIT {SERIES_SERVER_MAX}"
    )
    rows = _clean_rows(db.fetch_all(sql, tuple(params)))
    meta = {
        "source": source,
        "group_by": group_by,
        "metrics": metrics,
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
        "columns": list(group_by) + list(metrics),
    }
    return _maybe_artifact(
        kind="series_build",
        title=f"series {source} {','.join(metrics)}",
        rows=rows,
        meta=meta,
        max_rows=min(max_rows, SERIES_INLINE_MAX),
        force_artifact=force_artifact,
    )


def _ranks(values: list[float]) -> list[float]:
    """Average ranks for ties (1-based)."""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    return _pearson(_ranks(xs), _ranks(ys))


def _pair_and_stats(
    *,
    left: dict[Any, Any],
    right: dict[Any, Any],
    key_name: str,
) -> tuple[list[dict], list[float], list[float]]:
    keys = sorted(set(left) & set(right), key=lambda k: str(k))
    pairs: list[dict] = []
    xs: list[float] = []
    ys: list[float] = []
    for key in keys:
        vx, vy = left[key], right[key]
        try:
            fx, fy = float(vx), float(vy)
        except (TypeError, ValueError):
            continue
        if math.isnan(fx) or math.isnan(fy):
            continue
        xs.append(fx)
        ys.append(fy)
        pairs.append({key_name: key, "x": fx, "y": fy})
    return pairs, xs, ys


def correlate(
    metric_x: str,
    metric_y: str,
    source: Source = "detalhe",
    y_source: SeriesY = "metric",
    align_by: AlignBy = "ano",
    method: str = "both",
    ano_eleicao: int | None = None,
    nr_turno: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    nr_zona: int | None = None,
    cd_cargo: int | None = None,
    sg_partido: str | None = None,
) -> dict:
    """Correlaciona métrica eleitoral com outra série (Pearson/Spearman).

    WHEN TO USE: nulos×válidos; taxa×população; taxa/votos×PIB ou IDHM.
    WHEN NOT TO USE: <5 pontos; IDHM em série temporal (só 3 censos — use align_by=municipio).
    COST: medium (resumo + amostra; painel longo vira artifact).

    y_source: metric | populacao | pib | idhm
    align_by: ano (série no município) | municipio (corte transversal na UF/ano)
    metric_y PIB: pib_mil | pib_per_capita
    metric_y IDHM: idhm | idhm_renda | idhm_longevidade | idhm_educacao
    """
    if source not in ("votacao", "detalhe"):
        raise ValueError("source deve ser 'votacao' ou 'detalhe'")
    if y_source not in ("metric", "populacao", "pib", "idhm"):
        raise ValueError("y_source deve ser 'metric' | 'populacao' | 'pib' | 'idhm'")
    if align_by not in ("ano", "municipio"):
        raise ValueError("align_by deve ser 'ano' ou 'municipio'")
    if method not in ("pearson", "spearman", "both"):
        raise ValueError("method: pearson | spearman | both")

    allowed_x = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE
    if metric_x not in allowed_x:
        raise ValueError(f"metric_x inválida. Permitidas: {sorted(allowed_x)}")

    if y_source == "metric":
        if metric_y not in allowed_x:
            raise ValueError(f"metric_y inválida. Permitidas: {sorted(allowed_x)}")
    elif y_source == "populacao":
        if metric_y != "populacao":
            raise ValueError("Com y_source=populacao use metric_y='populacao'")
    elif y_source == "pib":
        if metric_y not in PIB_METRICS:
            raise ValueError(f"Com y_source=pib use metric_y em {sorted(PIB_METRICS)}")
    else:
        if metric_y not in IDHM_METRICS:
            raise ValueError(f"Com y_source=idhm use metric_y em {sorted(IDHM_METRICS)}")

    socio_ano_used: int | None = None
    key_name = "ano_eleicao" if align_by == "ano" else "id_municipio"

    if align_by == "municipio":
        if ano_eleicao is None:
            raise ValueError("align_by=municipio exige ano_eleicao")
        if not sg_uf:
            raise ValueError(
                "align_by=municipio exige sg_uf (corte por UF; evita varredura nacional)."
            )
        if y_source == "metric":
            raise ValueError(
                "align_by=municipio com y_source=metric não suportado; "
                "use y_source=pib|idhm|populacao ou align_by=ano."
            )
        if y_source == "populacao":
            raise ValueError(
                "align_by=municipio com populacao: use get_populacao + agregação manual "
                "ou y_source=pib|idhm (recomendado para Base 4)."
            )

        sx = _fetch_metric_by_municipio(
            source=source,
            metric=metric_x,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            limit=SERIES_SERVER_MAX,
        )
        by_x = {
            str(r["id_municipio"]).zfill(7): r[metric_x]
            for r in sx
            if r.get("id_municipio") is not None and r.get(metric_x) is not None
        }
        if y_source == "pib":
            sy, socio_ano_used = _fetch_pib_by_municipio(
                metric_y=metric_y,
                ano=ano_eleicao,
                sg_uf=sg_uf,
                limit=SERIES_SERVER_MAX,
            )
        else:
            sy, socio_ano_used = _fetch_idhm_by_municipio(
                metric_y=metric_y,
                ano=ano_eleicao,
                sg_uf=sg_uf,
                limit=SERIES_SERVER_MAX,
            )
        by_y = {
            str(r["id_municipio"]).zfill(7): r["value"]
            for r in sy
            if r.get("id_municipio") is not None and r.get("value") is not None
        }
        pairs, xs, ys = _pair_and_stats(left=by_x, right=by_y, key_name=key_name)
    else:
        # align_by=ano — série temporal
        if y_source in ("populacao", "pib", "idhm") and not id_municipio:
            raise ValueError(f"y_source={y_source} com align_by=ano exige id_municipio")
        if y_source == "idhm":
            raise ValueError(
                "IDHM só tem 1991/2000/2010 (<5 pontos em série). "
                "Use align_by=municipio com sg_uf + ano_eleicao."
            )

        sx = _fetch_metric_series(
            source=source,
            metric=metric_x,
            group_by=["ano_eleicao"],
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            nr_zona=nr_zona,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            limit=SERIES_SERVER_MAX,
        )
        by_x = {
            int(r["ano_eleicao"]): r[metric_x]
            for r in sx
            if r.get("ano_eleicao") is not None and r.get(metric_x) is not None
        }

        if y_source == "metric":
            sy = _fetch_metric_series(
                source=source,
                metric=metric_y,
                group_by=["ano_eleicao"],
                ano_eleicao=ano_eleicao,
                nr_turno=nr_turno,
                sg_uf=sg_uf,
                id_municipio=id_municipio,
                cd_municipio_tse=cd_municipio_tse,
                nr_zona=nr_zona,
                cd_cargo=cd_cargo,
                sg_partido=sg_partido,
                limit=SERIES_SERVER_MAX,
            )
            by_y = {
                int(r["ano_eleicao"]): r[metric_y]
                for r in sy
                if r.get("ano_eleicao") is not None and r.get(metric_y) is not None
            }
        elif y_source == "populacao":
            sy = _fetch_populacao_series(
                id_municipio=id_municipio,  # type: ignore[arg-type]
                anos=sorted(by_x.keys()) or None,
            )
            by_y = {
                int(r["ano_eleicao"]): r["populacao"]
                for r in sy
                if r.get("ano_eleicao") is not None and r.get("populacao") is not None
            }
        else:
            sy = _fetch_pib_series(
                id_municipio=id_municipio,  # type: ignore[arg-type]
                metric_y=metric_y,
                anos=sorted(by_x.keys()) or None,
            )
            by_y = {
                int(r["ano_eleicao"]): r["value"]
                for r in sy
                if r.get("ano_eleicao") is not None and r.get("value") is not None
            }

        pairs, xs, ys = _pair_and_stats(left=by_x, right=by_y, key_name=key_name)

    n = len(pairs)
    if n < CORRELATE_MIN_POINTS:
        raise ValueError(
            f"Só {n} pontos alinhados (mínimo {CORRELATE_MIN_POINTS}). "
            "Com PIB/IDHM prefira align_by=municipio + sg_uf + ano_eleicao; "
            "em série temporal use município com vários anos eleitorais."
        )

    pearson = _pearson(xs, ys) if method in ("pearson", "both") else None
    spearman = _spearman(xs, ys) if method in ("spearman", "both") else None

    panel_meta = {
        "metric_x": metric_x,
        "metric_y": metric_y,
        "y_source": y_source,
        "align_by": align_by,
        "source": source,
        "n": n,
        "socio_ano_used": socio_ano_used,
        "keys": [p[key_name] for p in pairs],
        "filters": {
            "ano_eleicao": ano_eleicao,
            "nr_turno": nr_turno,
            "sg_uf": sg_uf,
            "id_municipio": id_municipio,
            "cd_cargo": cd_cargo,
            "sg_partido": sg_partido,
        },
    }
    artifact_id = None
    if n > SERIES_INLINE_MAX:
        artifact_id = art.save_artifact(
            kind="correlate_panel",
            title=f"correlate {metric_x} vs {metric_y} ({align_by})",
            columns=[key_name, "x", "y"],
            rows=pairs,
            meta=panel_meta,
        )

    out: dict[str, Any] = {
        "mode": "summary",
        "n": n,
        "align_by": align_by,
        "pearson_r": round(pearson, 6) if pearson is not None else None,
        "spearman_rho": round(spearman, 6) if spearman is not None else None,
        "metric_x": metric_x,
        "metric_y": metric_y,
        "y_source": y_source,
        "sample": pairs[:SAMPLE_SIZE],
        "artifact_id": artifact_id,
        "hint": (
            "Interprete r próximo de ±1 como associação linear forte; "
            "não implica causalidade. IDHM usa o censo mais próximo do ano eleitoral."
        ),
        "cost": "medium",
    }
    if align_by == "ano":
        out["anos"] = [p["ano_eleicao"] for p in pairs]
    else:
        out["ano_eleicao"] = ano_eleicao
        out["socio_ano_used"] = socio_ano_used
        out["sg_uf"] = sg_uf.upper() if sg_uf else None
    return out


def series_compare(
    metric: str,
    source: Source = "detalhe",
    ano_eleicao: int | None = None,
    nr_turno: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    nr_zona: int | None = None,
    cd_cargo: int | None = None,
    sg_partido: str | None = None,
    max_rows: int | None = 50,
) -> dict:
    """Compara série ano a ano (delta e variação %).

    WHEN TO USE: ver se nulos/comparecimento sobem ou caem entre eleições.
    WHEN NOT TO USE: correlação entre duas métricas — use correlate.
    COST: medium.
    """
    if source not in ("votacao", "detalhe"):
        raise ValueError("source deve ser 'votacao' ou 'detalhe'")
    allowed = ALLOWED_METRICS_VOTACAO if source == "votacao" else ALLOWED_METRICS_DETALHE
    if metric not in allowed:
        raise ValueError(f"metric inválida. Permitidas: {sorted(allowed)}")

    rows = _fetch_metric_series(
        source=source,
        metric=metric,
        group_by=["ano_eleicao"],
        ano_eleicao=ano_eleicao,
        nr_turno=nr_turno,
        sg_uf=sg_uf,
        id_municipio=id_municipio,
        cd_municipio_tse=cd_municipio_tse,
        nr_zona=nr_zona,
        cd_cargo=cd_cargo,
        sg_partido=sg_partido,
        limit=SERIES_SERVER_MAX,
    )
    out: list[dict] = []
    prev_val: float | None = None
    prev_ano: int | None = None
    for r in rows:
        ano = r.get("ano_eleicao")
        val = r.get(metric)
        if ano is None or val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        delta = None if prev_val is None else fval - prev_val
        pct = None
        if prev_val not in (None, 0):
            pct = (fval - prev_val) / abs(prev_val)
        out.append(
            {
                "ano_eleicao": int(ano),
                "value": fval,
                "prev_ano": prev_ano,
                "delta": delta,
                "pct_change": round(pct, 6) if pct is not None else None,
            }
        )
        prev_val = fval
        prev_ano = int(ano)

    max_rows = clamp_max_rows(max_rows)
    meta = {
        "metric": metric,
        "source": source,
        "filters": {
            "id_municipio": id_municipio,
            "cd_cargo": cd_cargo,
            "nr_turno": nr_turno,
            "sg_uf": sg_uf,
        },
        "columns": ["ano_eleicao", "value", "prev_ano", "delta", "pct_change"],
    }
    return _maybe_artifact(
        kind="series_compare",
        title=f"yoy {metric}",
        rows=out,
        meta=meta,
        max_rows=min(max_rows, SERIES_INLINE_MAX),
    )
