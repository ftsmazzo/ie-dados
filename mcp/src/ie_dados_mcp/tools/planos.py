"""Tools tipadas — Acervo Planos de Governo."""

from __future__ import annotations

from ie_dados_mcp import db

CARGOS_EXEC = {1, 3, 11}


def plano_search_meta(
    ano_eleicao: int | None = None,
    cd_cargo: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    eleito: bool | None = None,
    sq_candidato: int | None = None,
    q: str | None = None,
    limit: int = 30,
) -> dict:
    """Busca metadados de planos de governo (catálogo).

    WHEN TO USE: listar planos por ano/cargo/UF/`eleito` antes do retrieve.
    WHEN NOT TO USE: pergunta temática no texto — use plano_retrieve.
    COST: cheap.
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit deve estar entre 1 e 100")
    if cd_cargo is not None and cd_cargo not in CARGOS_EXEC:
        raise ValueError("cd_cargo executivo: 1 Presidente, 3 Governador, 11 Prefeito")

    clauses: list[str] = []
    params: list = []
    if ano_eleicao is not None:
        clauses.append("ano_eleicao = %s")
        params.append(ano_eleicao)
    if cd_cargo is not None:
        clauses.append("cd_cargo = %s")
        params.append(cd_cargo)
    if sg_uf:
        clauses.append("sg_uf = %s")
        params.append(sg_uf.upper())
    if id_municipio:
        clauses.append("id_municipio = %s")
        params.append(id_municipio.zfill(7))
    if eleito is not None:
        clauses.append("eleito = %s")
        params.append(eleito)
    if sq_candidato is not None:
        clauses.append("sq_candidato = %s")
        params.append(sq_candidato)
    if q:
        clauses.append("(nm_candidato ILIKE %s OR arquivo_nome ILIKE %s OR sg_partido ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    rows = db.fetch_all(
        f"""
        SELECT id_plano, ano_eleicao, cd_cargo, ds_cargo, sg_uf, id_municipio,
               sq_candidato, nm_candidato, sg_partido, eleito, ds_sit_tot_turno,
               arquivo_nome, n_chunks, indexado_em
        FROM ref.plano_governo
        {where}
        ORDER BY
          CASE WHEN ano_eleicao = 2026 AND cd_cargo = 1 AND eleito THEN 0
               WHEN eleito THEN 1 ELSE 2 END,
          ano_eleicao DESC, nm_candidato NULLS LAST
        LIMIT %s
        """,
        tuple(params),
    )
    return {"rows": rows, "n": len(rows), "cost": "cheap"}


def plano_retrieve(
    query: str,
    ano_eleicao: int | None = None,
    cd_cargo: int | None = None,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    eleito: bool | None = None,
    limit: int = 8,
) -> dict:
    """Recupera trechos do acervo (FTS português) com citação do plano.

    WHEN TO USE: pergunta temática (saúde, educação, segurança…).
    WHEN NOT TO USE: só metadados — use plano_search_meta.
    COST: medium.
    """
    if not query or not query.strip():
        raise ValueError("query obrigatória")
    if limit < 1 or limit > 30:
        raise ValueError("limit deve estar entre 1 e 30")

    clauses = ["c.tsv @@ plainto_tsquery('portuguese', %s)"]
    params: list = [query]
    if ano_eleicao is not None:
        clauses.append("p.ano_eleicao = %s")
        params.append(ano_eleicao)
    if cd_cargo is not None:
        clauses.append("p.cd_cargo = %s")
        params.append(cd_cargo)
    if sg_uf:
        clauses.append("p.sg_uf = %s")
        params.append(sg_uf.upper())
    if id_municipio:
        clauses.append("p.id_municipio = %s")
        params.append(id_municipio.zfill(7))
    if eleito is not None:
        clauses.append("p.eleito = %s")
        params.append(eleito)

    params.append(limit)
    rows = db.fetch_all(
        f"""
        SELECT
          c.id_chunk, c.chunk_ord, c.secao,
          left(c.texto, 800) AS trecho,
          ts_rank(c.tsv, plainto_tsquery('portuguese', %s)) AS rank,
          p.id_plano, p.ano_eleicao, p.cd_cargo, p.ds_cargo, p.sg_uf,
          p.id_municipio, p.sq_candidato, p.nm_candidato, p.sg_partido,
          p.eleito, p.arquivo_nome
        FROM docs.plano_chunk c
        JOIN ref.plano_governo p ON p.id_plano = c.id_plano
        WHERE {" AND ".join(clauses)}
        ORDER BY rank DESC, p.eleito DESC, p.ano_eleicao DESC
        LIMIT %s
        """,
        tuple([query] + params),
    )
    return {
        "query": query,
        "hits": rows,
        "n": len(rows),
        "hint": "Cite sempre id_plano/arquivo_nome/sq_candidato ao usar o trecho.",
        "cost": "medium",
    }


def plano_compare_tema(
    query: str,
    ano_eleicao: int | None = None,
    cd_cargo: int | None = None,
    sg_uf: str | None = None,
    only_eleito: bool = True,
    max_planos: int = 5,
    trechos_por_plano: int = 2,
) -> dict:
    """Compara o mesmo tema em N planos (padrão: só eleitos).

    WHEN TO USE: boas práticas / contraste entre propostas vencedoras.
    WHEN NOT TO USE: busca livre sem contraste — use plano_retrieve.
    COST: medium.
    """
    if not query or not query.strip():
        raise ValueError("query obrigatória")
    if max_planos < 2 or max_planos > 10:
        raise ValueError("max_planos entre 2 e 10")
    if trechos_por_plano < 1 or trechos_por_plano > 5:
        raise ValueError("trechos_por_plano entre 1 e 5")

    # top planos distintos pelo melhor rank
    clauses = ["c.tsv @@ plainto_tsquery('portuguese', %s)"]
    where_params: list = [query]
    if only_eleito:
        clauses.append("p.eleito = TRUE")
    if ano_eleicao is not None:
        clauses.append("p.ano_eleicao = %s")
        where_params.append(ano_eleicao)
    if cd_cargo is not None:
        clauses.append("p.cd_cargo = %s")
        where_params.append(cd_cargo)
    if sg_uf:
        clauses.append("p.sg_uf = %s")
        where_params.append(sg_uf.upper())

    # SELECT rank(query) … WHERE …query…filters… LIMIT
    top = db.fetch_all(
        f"""
        SELECT p.id_plano,
               max(ts_rank(c.tsv, plainto_tsquery('portuguese', %s))) AS best_rank
        FROM docs.plano_chunk c
        JOIN ref.plano_governo p ON p.id_plano = c.id_plano
        WHERE {" AND ".join(clauses)}
        GROUP BY p.id_plano
        ORDER BY best_rank DESC
        LIMIT %s
        """,
        tuple([query] + where_params + [max_planos]),
    )
    planos = []
    for t in top:
        pid = t["id_plano"]
        hits = db.fetch_all(
            """
            SELECT c.chunk_ord, left(c.texto, 600) AS trecho,
                   ts_rank(c.tsv, plainto_tsquery('portuguese', %s)) AS rank,
                   p.ano_eleicao, p.cd_cargo, p.ds_cargo, p.sg_uf, p.id_municipio,
                   p.sq_candidato, p.nm_candidato, p.sg_partido, p.eleito, p.arquivo_nome
            FROM docs.plano_chunk c
            JOIN ref.plano_governo p ON p.id_plano = c.id_plano
            WHERE c.id_plano = %s AND c.tsv @@ plainto_tsquery('portuguese', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            (query, pid, query, trechos_por_plano),
        )
        if hits:
            meta = {k: hits[0][k] for k in (
                "ano_eleicao", "cd_cargo", "ds_cargo", "sg_uf", "id_municipio",
                "sq_candidato", "nm_candidato", "sg_partido", "eleito", "arquivo_nome",
            )}
            planos.append(
                {
                    "id_plano": pid,
                    "meta": meta,
                    "trechos": [
                        {"chunk_ord": h["chunk_ord"], "trecho": h["trecho"], "rank": h["rank"]}
                        for h in hits
                    ],
                }
            )

    return {
        "query": query,
        "only_eleito": only_eleito,
        "n_planos": len(planos),
        "planos": planos,
        "cost": "medium",
    }


def plano_seed_ideia(
    tema: str,
    ano_eleicao: int | None = 2026,
    cd_cargo: int | None = 1,
    sg_uf: str | None = None,
    id_municipio: str | None = None,
    max_fontes: int = 5,
) -> dict:
    """Monta esqueleto de ideia a partir de planos **eleitos** (com fontes).

    WHEN TO USE: rascunho inicial de proposta temática baseado em quem venceu.
    WHEN NOT TO USE: afirmar fato sem trecho — só use as fontes devolvidas.
    COST: medium.

    Default: Presidente eleito 2026 (mandato atual). Para prefeito, passe cd_cargo=11 + id_municipio.
    """
    if not tema or not tema.strip():
        raise ValueError("tema obrigatório")
    if max_fontes < 1 or max_fontes > 10:
        raise ValueError("max_fontes entre 1 e 10")

    cmp = plano_compare_tema(
        query=tema,
        ano_eleicao=ano_eleicao,
        cd_cargo=cd_cargo,
        sg_uf=sg_uf,
        only_eleito=True,
        max_planos=max_fontes,
        trechos_por_plano=2,
    )
    fontes = []
    bullets: list[str] = []
    for p in cmp.get("planos") or []:
        m = p["meta"]
        fontes.append(
            {
                "id_plano": p["id_plano"],
                "ano_eleicao": m.get("ano_eleicao"),
                "nm_candidato": m.get("nm_candidato"),
                "sg_partido": m.get("sg_partido"),
                "cd_cargo": m.get("cd_cargo"),
                "sg_uf": m.get("sg_uf"),
                "arquivo_nome": m.get("arquivo_nome"),
                "sq_candidato": m.get("sq_candidato"),
            }
        )
        for t in p.get("trechos") or []:
            snippet = (t.get("trecho") or "").strip().replace("\n", " ")
            if len(snippet) > 220:
                snippet = snippet[:217] + "..."
            bullets.append(
                f"- ({m.get('nm_candidato') or m.get('sq_candidato')}, {m.get('ano_eleicao')}): {snippet}"
            )

    outline = {
        "tema": tema,
        "escopo": {
            "ano_eleicao": ano_eleicao,
            "cd_cargo": cd_cargo,
            "sg_uf": sg_uf,
            "id_municipio": id_municipio,
            "somente_eleitos": True,
        },
        "estrutura_sugerida": [
            "Diagnóstico do território (cruzar PIB/IDHM se houver id_municipio)",
            "Objetivo mensurável no tema",
            "Ações inspiradas nas fontes eleitas (abaixo)",
            "Indicadores de acompanhamento",
            "Riscos e premissas",
        ],
        "insights_de_fontes": bullets[:12],
        "fontes": fontes,
        "aviso": (
            "Rascunho baseado só nos trechos citados. Não invente números ou metas "
            "que não estejam nas fontes. Presidente atual: planos eleitos de 2026."
        ),
    }
    return {"seed": outline, "n_fontes": len(fontes), "cost": "medium"}
