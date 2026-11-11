"""Tools tipadas — Acervo Municípios (RAG institucional)."""

from __future__ import annotations

from ie_dados_mcp import db

# slug → id_municipio (espelha scripts/load_acervo_municipio.py)
KNOWN = {
    "ribeirao-preto": "3543402",
    "3543402": "3543402",
}


def _resolve_mun(
    id_municipio: str | None = None,
    slug_municipio: str | None = None,
) -> tuple[str, str]:
    if id_municipio:
        mid = id_municipio.zfill(7)
        row = db.fetch_one(
            """
            SELECT id_municipio, slug_municipio
            FROM docs.municipio_doc
            WHERE id_municipio = %s
            LIMIT 1
            """,
            (mid,),
        )
        if not row:
            # fallback known map
            slug = next((s for s, m in KNOWN.items() if m == mid and not s.isdigit()), mid)
            return mid, slug
        return row["id_municipio"], row["slug_municipio"]
    if slug_municipio:
        slug = slug_municipio.strip().lower()
        mid = KNOWN.get(slug)
        if mid:
            return mid, slug
        row = db.fetch_one(
            """
            SELECT id_municipio, slug_municipio
            FROM docs.municipio_doc
            WHERE slug_municipio = %s
            LIMIT 1
            """,
            (slug,),
        )
        if not row:
            raise ValueError(f"Município não encontrado no acervo: {slug}")
        return row["id_municipio"], row["slug_municipio"]
    raise ValueError("Informe id_municipio ou slug_municipio")


def mun_list(limit: int = 50) -> dict:
    """Lista municípios presentes no Acervo Municípios.

    WHEN TO USE: início de sessão / descobrir slugs disponíveis.
    WHEN NOT TO USE: busca temática — use mun_retrieve.
    COST: cheap.
    """
    if limit < 1 or limit > 200:
        raise ValueError("limit entre 1 e 200")
    rows = db.fetch_all(
        """
        SELECT d.id_municipio, d.slug_municipio,
               m.nome, m.sigla_uf,
               COUNT(*) AS n_docs,
               COUNT(*) FILTER (WHERE d.tipo = 'secretaria') AS n_secretarias
        FROM docs.municipio_doc d
        LEFT JOIN ref.municipio m ON m.id_municipio = d.id_municipio
        GROUP BY d.id_municipio, d.slug_municipio, m.nome, m.sigla_uf
        ORDER BY m.nome NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )
    return {"municipios": rows, "n": len(rows), "cost": "cheap"}


def mun_list_secretarias(
    id_municipio: str | None = None,
    slug_municipio: str | None = None,
) -> dict:
    """Lista secretarias/órgãos indexados de um município.

    WHEN TO USE: antes de mun_get_secretaria ou para mapear a estrutura.
    WHEN NOT TO USE: sem município — sempre escopo obrigatório.
    COST: cheap.
    """
    mid, slug = _resolve_mun(id_municipio, slug_municipio)
    rows = db.fetch_all(
        """
        SELECT secretaria_slug,
               MAX(titulo) FILTER (WHERE tipo = 'secretaria') AS titulo,
               COUNT(*) AS n_docs,
               COUNT(*) FILTER (WHERE tipo = 'servico') AS n_servicos
        FROM docs.municipio_doc
        WHERE id_municipio = %s AND secretaria_slug IS NOT NULL
        GROUP BY secretaria_slug
        ORDER BY titulo NULLS LAST, secretaria_slug
        """,
        (mid,),
    )
    return {
        "id_municipio": mid,
        "slug_municipio": slug,
        "secretarias": rows,
        "n": len(rows),
        "cost": "cheap",
    }


def mun_get_secretaria(
    secretaria_slug: str,
    id_municipio: str | None = None,
    slug_municipio: str | None = None,
    trechos: int = 3,
) -> dict:
    """Ficha da secretaria (meta + trechos principais do MD).

    WHEN TO USE: “o que faz a Secretaria X / quem é o secretário / contato”.
    WHEN NOT TO USE: pergunta aberta multi-secretaria — use mun_retrieve.
    COST: cheap.
    """
    if not secretaria_slug:
        raise ValueError("secretaria_slug obrigatório")
    mid, slug = _resolve_mun(id_municipio, slug_municipio)
    sec = secretaria_slug.strip().lower()
    docs = db.fetch_all(
        """
        SELECT id_doc, tipo, titulo, path_md, url_fonte, n_chunks, scraped_at
        FROM docs.municipio_doc
        WHERE id_municipio = %s AND secretaria_slug = %s
        ORDER BY CASE tipo WHEN 'secretaria' THEN 0 WHEN 'servico' THEN 1 ELSE 2 END,
                 titulo
        """,
        (mid, sec),
    )
    if not docs:
        raise ValueError(f"Secretaria '{sec}' não encontrada em {slug}")
    main = next((d for d in docs if d["tipo"] == "secretaria"), docs[0])
    hits = db.fetch_all(
        """
        SELECT chunk_ord, left(texto, 900) AS trecho
        FROM docs.municipio_chunk
        WHERE id_doc = %s
        ORDER BY chunk_ord
        LIMIT %s
        """,
        (main["id_doc"], max(1, min(trechos, 10))),
    )
    return {
        "id_municipio": mid,
        "slug_municipio": slug,
        "secretaria_slug": sec,
        "ficha": main,
        "docs_relacionados": docs,
        "trechos": hits,
        "cost": "cheap",
    }


def mun_retrieve(
    query: str,
    id_municipio: str | None = None,
    slug_municipio: str | None = None,
    secretaria_slug: str | None = None,
    tipo: str | None = None,
    limit: int = 8,
) -> dict:
    """Busca FTS no acervo do município (com citação).

    WHEN TO USE: perguntas temáticas sobre o município (“dengue”, “IPTU”, “UBS”).
    WHEN NOT TO USE: sem município; listar secretarias — use mun_list_secretarias.
    COST: medium.
    """
    if not query or not query.strip():
        raise ValueError("query obrigatória")
    if limit < 1 or limit > 30:
        raise ValueError("limit entre 1 e 30")
    mid, slug = _resolve_mun(id_municipio, slug_municipio)

    clauses = [
        "c.tsv @@ plainto_tsquery('portuguese', %s)",
        "d.id_municipio = %s",
    ]
    where_params: list = [query, mid]
    if secretaria_slug:
        clauses.append("d.secretaria_slug = %s")
        where_params.append(secretaria_slug.strip().lower())
    if tipo:
        clauses.append("d.tipo = %s")
        where_params.append(tipo)

    rows = db.fetch_all(
        f"""
        SELECT
          ts_rank(c.tsv, plainto_tsquery('portuguese', %s)) AS rank,
          c.chunk_ord, left(c.texto, 900) AS trecho,
          d.id_doc, d.tipo, d.titulo, d.secretaria_slug, d.path_md, d.url_fonte
        FROM docs.municipio_chunk c
        JOIN docs.municipio_doc d ON d.id_doc = c.id_doc
        WHERE {" AND ".join(clauses)}
        ORDER BY rank DESC
        LIMIT %s
        """,
        tuple([query] + where_params + [limit]),
    )
    return {
        "id_municipio": mid,
        "slug_municipio": slug,
        "query": query,
        "hits": rows,
        "n": len(rows),
        "hint": "Cite path_md/url_fonte ao responder.",
        "cost": "medium",
    }


def mun_search_servico(
    query: str,
    id_municipio: str | None = None,
    slug_municipio: str | None = None,
    secretaria_slug: str | None = None,
    limit: int = 8,
) -> dict:
    """Atalho de retrieve focado em páginas tipo=servico.

    WHEN TO USE: “como emitir IPTU / onde renovar / posto de atendimento”.
    WHEN NOT TO USE: competência genérica da secretaria — use mun_get_secretaria.
    COST: medium.
    """
    return mun_retrieve(
        query=query,
        id_municipio=id_municipio,
        slug_municipio=slug_municipio,
        secretaria_slug=secretaria_slug,
        tipo="servico",
        limit=limit,
    )
