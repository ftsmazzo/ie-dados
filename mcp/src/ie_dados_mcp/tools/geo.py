from __future__ import annotations

from ie_dados_mcp import db


def resolve_municipio(
    nome: str | None = None,
    sigla_uf: str | None = None,
    id_municipio: str | None = None,
    cd_municipio_tse: int | None = None,
    limit: int = 10,
) -> dict:
    """Resolve município para id_municipio IBGE (e código TSE quando houver).

    WHEN TO USE: antes de qualquer consulta eleitoral/populacional por município.
    WHEN NOT TO USE: não use para listar o Brasil inteiro — filtre por UF ou nome.
    COST: cheap.
    """
    if limit < 1 or limit > 50:
        raise ValueError("limit deve estar entre 1 e 50")

    if id_municipio:
        rows = db.fetch_all(
            """
            SELECT m.id_municipio, m.nome, m.sigla_uf, t.cd_municipio_tse
            FROM ref.municipio m
            LEFT JOIN ref.municipio_tse t ON t.id_municipio = m.id_municipio
            WHERE m.id_municipio = %s
            LIMIT %s
            """,
            (id_municipio.zfill(7), limit),
        )
        return {"matches": rows, "n": len(rows)}

    if cd_municipio_tse is not None:
        rows = db.fetch_all(
            """
            SELECT m.id_municipio, m.nome, m.sigla_uf, t.cd_municipio_tse
            FROM ref.municipio_tse t
            JOIN ref.municipio m ON m.id_municipio = t.id_municipio
            WHERE t.cd_municipio_tse = %s
            LIMIT %s
            """,
            (cd_municipio_tse, limit),
        )
        return {"matches": rows, "n": len(rows)}

    if not nome:
        raise ValueError("Informe nome, id_municipio ou cd_municipio_tse")

    params: list = [f"%{nome}%"]
    sql = """
        SELECT m.id_municipio, m.nome, m.sigla_uf, t.cd_municipio_tse
        FROM ref.municipio m
        LEFT JOIN ref.municipio_tse t ON t.id_municipio = m.id_municipio
        WHERE m.nome ILIKE %s
    """
    if sigla_uf:
        sql += " AND m.sigla_uf = %s"
        params.append(sigla_uf.upper())
    sql += " ORDER BY m.nome LIMIT %s"
    params.append(limit)
    rows = db.fetch_all(sql, tuple(params))
    return {"matches": rows, "n": len(rows)}


def get_populacao(
    id_municipio: str | None = None,
    sigla_uf: str | None = None,
    ano: int = 2024,
    limit: int = 50,
) -> dict:
    """Retorna população municipal (estimativa IBGE).

    WHEN TO USE: após resolve_municipio, para cruzar demografia com voto.
    WHEN NOT TO USE: sem filtro de município ou UF (estoura volume).
    COST: cheap.
    """
    if limit < 1 or limit > 200:
        raise ValueError("limit deve estar entre 1 e 200")
    if not id_municipio and not sigla_uf:
        raise ValueError("Informe id_municipio ou sigla_uf")

    if id_municipio:
        rows = db.fetch_all(
            """
            SELECT p.id_municipio, m.nome, m.sigla_uf, p.ano, p.populacao, p.fonte
            FROM ref.populacao_municipio p
            JOIN ref.municipio m ON m.id_municipio = p.id_municipio
            WHERE p.id_municipio = %s AND p.ano = %s
            """,
            (id_municipio.zfill(7), ano),
        )
        return {"rows": rows, "n": len(rows), "ano": ano}

    rows = db.fetch_all(
        """
        SELECT p.id_municipio, m.nome, m.sigla_uf, p.ano, p.populacao, p.fonte
        FROM ref.populacao_municipio p
        JOIN ref.municipio m ON m.id_municipio = p.id_municipio
        WHERE m.sigla_uf = %s AND p.ano = %s
        ORDER BY p.populacao DESC
        LIMIT %s
        """,
        (sigla_uf.upper(), ano, limit),
    )
    return {"rows": rows, "n": len(rows), "ano": ano, "sigla_uf": sigla_uf.upper()}
