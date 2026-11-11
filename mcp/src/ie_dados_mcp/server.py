from __future__ import annotations

import os
import secrets
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.types import ASGIApp

from ie_dados_mcp import db
from ie_dados_mcp.tools import analytics as analytics_tools
from ie_dados_mcp.tools import artifacts as art_tools
from ie_dados_mcp.tools import catalog as catalog_tools
from ie_dados_mcp.tools import election as election_tools
from ie_dados_mcp.tools import finance as finance_tools
from ie_dados_mcp.tools import geo as geo_tools
from ie_dados_mcp.tools import municipios as municipios_tools
from ie_dados_mcp.tools import planos as planos_tools


def _transport_security() -> TransportSecuritySettings:
    """DNS rebinding: atrás de proxy + Bearer. Hosts extras via MCP_ALLOWED_HOSTS."""
    raw = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()
    if not raw:
        # BearerAuthMiddleware já protege /mcp*; Host check localhost quebraria o domínio público.
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    origins: list[str] = []
    for h in hosts:
        base = h.split(":")[0]
        origins.extend([f"https://{base}", f"http://{base}", f"https://{h}", f"http://{h}"])
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def _mcp_token() -> str:
    token = os.environ.get("MCP_TOKEN", "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        os.environ["MCP_TOKEN"] = token
        print(
            "WARNING: MCP_TOKEN não definido; gerado efêmero para este processo",
            flush=True,
        )
    return token


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Exige Authorization: Bearer <MCP_TOKEN> em /mcp*; libera /health*."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path.startswith("/health"):
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse({"error": "missing_bearer"}, status_code=401)
        got = auth.split(" ", 1)[1].strip()
        if not secrets.compare_digest(got, self.token):
            return JSONResponse({"error": "invalid_token"}, status_code=401)
        return await call_next(request)


def build_server() -> MCPServer:
    mcp = MCPServer(
        name="ie-dados",
        title="IE Dados MCP",
        description=(
            "Consulta tipada e agregada da base ie-dados (municípios, população, "
            "resultados eleitorais mun/zona). Sem SQL livre. Sempre estime antes de agregar."
        ),
        instructions=(
            "Fluxo sugerido: list_domains → describe_domain → "
            "resolve_municipio → election_estimate → election_aggregate. "
            "Para séries/correlação: series_build → correlate / series_compare. "
            "Planos de governo: plano_search_meta → plano_retrieve / "
            "plano_compare_tema / plano_seed_ideia (Presidente atual = eleito 2026). "
            "Acervo município: mun_list → mun_list_secretarias → "
            "mun_get_secretaria / mun_retrieve / mun_search_servico. "
            "Se vier artifact_id, use artifact_get. "
            "Nunca peça dump cru de votacao_candidato_munzona."
        ),
        version="0.4.0",
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @mcp.custom_route("/health/ready", methods=["GET"])
    async def ready(_request: Request) -> JSONResponse:
        try:
            db.fetch_one("SELECT 1 AS ok")
            return JSONResponse({"status": "ready"})
        except Exception as e:
            return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)

    @mcp.tool(
        name="list_domains",
        description=catalog_tools.list_domains.__doc__ or "Lista domínios.",
    )
    def list_domains() -> dict[str, Any]:
        return catalog_tools.list_domains()

    @mcp.tool(
        name="describe_domain",
        description=catalog_tools.describe_domain.__doc__ or "Descreve um domínio.",
    )
    def describe_domain(domain_id: str) -> dict[str, Any]:
        return catalog_tools.describe_domain(domain_id)

    @mcp.tool(
        name="resolve_municipio",
        description=geo_tools.resolve_municipio.__doc__ or "Resolve município.",
    )
    def resolve_municipio(
        nome: str | None = None,
        sigla_uf: str | None = None,
        id_municipio: str | None = None,
        cd_municipio_tse: int | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return geo_tools.resolve_municipio(
            nome=nome,
            sigla_uf=sigla_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            limit=limit,
        )

    @mcp.tool(
        name="get_populacao",
        description=geo_tools.get_populacao.__doc__ or "População municipal.",
    )
    def get_populacao(
        id_municipio: str | None = None,
        sigla_uf: str | None = None,
        ano: int = 2024,
        limit: int = 50,
    ) -> dict[str, Any]:
        return geo_tools.get_populacao(
            id_municipio=id_municipio,
            sigla_uf=sigla_uf,
            ano=ano,
            limit=limit,
        )

    @mcp.tool(
        name="get_pib",
        description=geo_tools.get_pib.__doc__ or "PIB municipal IBGE.",
    )
    def get_pib(
        id_municipio: str | None = None,
        sigla_uf: str | None = None,
        ano: int = 2021,
        limit: int = 50,
    ) -> dict[str, Any]:
        return geo_tools.get_pib(
            id_municipio=id_municipio,
            sigla_uf=sigla_uf,
            ano=ano,
            limit=limit,
        )

    @mcp.tool(
        name="get_idhm",
        description=geo_tools.get_idhm.__doc__ or "IDHM municipal Atlas.",
    )
    def get_idhm(
        id_municipio: str | None = None,
        sigla_uf: str | None = None,
        ano: int = 2010,
        limit: int = 50,
    ) -> dict[str, Any]:
        return geo_tools.get_idhm(
            id_municipio=id_municipio,
            sigla_uf=sigla_uf,
            ano=ano,
            limit=limit,
        )

    @mcp.tool(
        name="election_estimate",
        description=election_tools.election_estimate.__doc__
        or "Estima tamanho da agregação.",
    )
    def election_estimate(
        source: str = "votacao",
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
    ) -> dict[str, Any]:
        if source not in ("votacao", "detalhe"):
            raise ValueError("source deve ser 'votacao' ou 'detalhe'")
        return election_tools.election_estimate(
            source=source,  # type: ignore[arg-type]
            group_by=group_by,
            metrics=metrics,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            nr_zona=nr_zona,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
        )

    @mcp.tool(
        name="election_aggregate",
        description=election_tools.election_aggregate.__doc__
        or "Agrega resultados eleitorais.",
    )
    def election_aggregate(
        source: str = "votacao",
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
    ) -> dict[str, Any]:
        if source not in ("votacao", "detalhe"):
            raise ValueError("source deve ser 'votacao' ou 'detalhe'")
        return election_tools.election_aggregate(
            source=source,  # type: ignore[arg-type]
            group_by=group_by,
            metrics=metrics,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            nr_zona=nr_zona,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            max_rows=max_rows,
            force_artifact=force_artifact,
        )

    @mcp.tool(
        name="finance_estimate",
        description=finance_tools.finance_estimate.__doc__
        or "Estima agregação financeira.",
    )
    def finance_estimate(
        source: str = "receita",
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
    ) -> dict[str, Any]:
        if source not in ("receita", "despesa", "paga", "doador"):
            raise ValueError("source: receita | despesa | paga | doador")
        return finance_tools.finance_estimate(
            source=source,  # type: ignore[arg-type]
            group_by=group_by,
            metrics=metrics,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            sq_candidato=sq_candidato,
        )

    @mcp.tool(
        name="finance_aggregate",
        description=finance_tools.finance_aggregate.__doc__
        or "Agrega receitas/despesas.",
    )
    def finance_aggregate(
        source: str = "receita",
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
    ) -> dict[str, Any]:
        if source not in ("receita", "despesa", "paga", "doador"):
            raise ValueError("source: receita | despesa | paga | doador")
        return finance_tools.finance_aggregate(
            source=source,  # type: ignore[arg-type]
            group_by=group_by,
            metrics=metrics,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            sq_candidato=sq_candidato,
            max_rows=max_rows,
            force_artifact=force_artifact,
        )

    @mcp.tool(
        name="finance_pago_contratado",
        description=finance_tools.finance_pago_contratado.__doc__
        or "Taxa pago sobre contratado.",
    )
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
    ) -> dict[str, Any]:
        return finance_tools.finance_pago_contratado(
            group_by=group_by,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            sq_candidato=sq_candidato,
            max_rows=max_rows,
            force_artifact=force_artifact,
        )

    @mcp.tool(
        name="mun_list",
        description=municipios_tools.mun_list.__doc__ or "Lista municípios no acervo.",
    )
    def mun_list(limit: int = 50) -> dict[str, Any]:
        return municipios_tools.mun_list(limit=limit)

    @mcp.tool(
        name="mun_list_secretarias",
        description=municipios_tools.mun_list_secretarias.__doc__
        or "Lista secretarias do município.",
    )
    def mun_list_secretarias(
        id_municipio: str | None = None,
        slug_municipio: str | None = None,
    ) -> dict[str, Any]:
        return municipios_tools.mun_list_secretarias(
            id_municipio=id_municipio,
            slug_municipio=slug_municipio,
        )

    @mcp.tool(
        name="mun_get_secretaria",
        description=municipios_tools.mun_get_secretaria.__doc__
        or "Ficha de uma secretaria.",
    )
    def mun_get_secretaria(
        secretaria_slug: str,
        id_municipio: str | None = None,
        slug_municipio: str | None = None,
        trechos: int = 3,
    ) -> dict[str, Any]:
        return municipios_tools.mun_get_secretaria(
            secretaria_slug=secretaria_slug,
            id_municipio=id_municipio,
            slug_municipio=slug_municipio,
            trechos=trechos,
        )

    @mcp.tool(
        name="mun_retrieve",
        description=municipios_tools.mun_retrieve.__doc__ or "FTS acervo município.",
    )
    def mun_retrieve(
        query: str,
        id_municipio: str | None = None,
        slug_municipio: str | None = None,
        secretaria_slug: str | None = None,
        tipo: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        return municipios_tools.mun_retrieve(
            query=query,
            id_municipio=id_municipio,
            slug_municipio=slug_municipio,
            secretaria_slug=secretaria_slug,
            tipo=tipo,
            limit=limit,
        )

    @mcp.tool(
        name="mun_search_servico",
        description=municipios_tools.mun_search_servico.__doc__
        or "Busca serviços municipais.",
    )
    def mun_search_servico(
        query: str,
        id_municipio: str | None = None,
        slug_municipio: str | None = None,
        secretaria_slug: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        return municipios_tools.mun_search_servico(
            query=query,
            id_municipio=id_municipio,
            slug_municipio=slug_municipio,
            secretaria_slug=secretaria_slug,
            limit=limit,
        )

    @mcp.tool(
        name="plano_search_meta",
        description=planos_tools.plano_search_meta.__doc__ or "Metadados de planos.",
    )
    def plano_search_meta(
        ano_eleicao: int | None = None,
        cd_cargo: int | None = None,
        sg_uf: str | None = None,
        id_municipio: str | None = None,
        eleito: bool | None = None,
        sq_candidato: int | None = None,
        q: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        return planos_tools.plano_search_meta(
            ano_eleicao=ano_eleicao,
            cd_cargo=cd_cargo,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            eleito=eleito,
            sq_candidato=sq_candidato,
            q=q,
            limit=limit,
        )

    @mcp.tool(
        name="plano_retrieve",
        description=planos_tools.plano_retrieve.__doc__ or "Retrieve FTS de planos.",
    )
    def plano_retrieve(
        query: str,
        ano_eleicao: int | None = None,
        cd_cargo: int | None = None,
        sg_uf: str | None = None,
        id_municipio: str | None = None,
        eleito: bool | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        return planos_tools.plano_retrieve(
            query=query,
            ano_eleicao=ano_eleicao,
            cd_cargo=cd_cargo,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            eleito=eleito,
            limit=limit,
        )

    @mcp.tool(
        name="plano_compare_tema",
        description=planos_tools.plano_compare_tema.__doc__ or "Compara tema entre planos.",
    )
    def plano_compare_tema(
        query: str,
        ano_eleicao: int | None = None,
        cd_cargo: int | None = None,
        sg_uf: str | None = None,
        only_eleito: bool = True,
        max_planos: int = 5,
        trechos_por_plano: int = 2,
    ) -> dict[str, Any]:
        return planos_tools.plano_compare_tema(
            query=query,
            ano_eleicao=ano_eleicao,
            cd_cargo=cd_cargo,
            sg_uf=sg_uf,
            only_eleito=only_eleito,
            max_planos=max_planos,
            trechos_por_plano=trechos_por_plano,
        )

    @mcp.tool(
        name="plano_seed_ideia",
        description=planos_tools.plano_seed_ideia.__doc__ or "Seed de ideia a partir de eleitos.",
    )
    def plano_seed_ideia(
        tema: str,
        ano_eleicao: int | None = 2026,
        cd_cargo: int | None = 1,
        sg_uf: str | None = None,
        id_municipio: str | None = None,
        max_fontes: int = 5,
    ) -> dict[str, Any]:
        return planos_tools.plano_seed_ideia(
            tema=tema,
            ano_eleicao=ano_eleicao,
            cd_cargo=cd_cargo,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            max_fontes=max_fontes,
        )

    @mcp.tool(
        name="series_build",
        description=analytics_tools.series_build.__doc__ or "Série temporal agregada.",
    )
    def series_build(
        source: str = "detalhe",
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
    ) -> dict[str, Any]:
        if source not in ("votacao", "detalhe"):
            raise ValueError("source deve ser 'votacao' ou 'detalhe'")
        return analytics_tools.series_build(
            source=source,  # type: ignore[arg-type]
            metrics=metrics,
            group_by=group_by,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            nr_zona=nr_zona,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            max_rows=max_rows,
            force_artifact=force_artifact,
        )

    @mcp.tool(
        name="correlate",
        description=analytics_tools.correlate.__doc__ or "Correlação tipada.",
    )
    def correlate(
        metric_x: str,
        metric_y: str,
        source: str = "detalhe",
        y_source: str = "metric",
        align_by: str = "ano",
        method: str = "both",
        ano_eleicao: int | None = None,
        nr_turno: int | None = None,
        sg_uf: str | None = None,
        id_municipio: str | None = None,
        cd_municipio_tse: int | None = None,
        nr_zona: int | None = None,
        cd_cargo: int | None = None,
        sg_partido: str | None = None,
    ) -> dict[str, Any]:
        if source not in ("votacao", "detalhe"):
            raise ValueError("source deve ser 'votacao' ou 'detalhe'")
        if y_source not in ("metric", "populacao", "pib", "idhm"):
            raise ValueError("y_source deve ser 'metric' | 'populacao' | 'pib' | 'idhm'")
        if align_by not in ("ano", "municipio"):
            raise ValueError("align_by deve ser 'ano' ou 'municipio'")
        return analytics_tools.correlate(
            metric_x=metric_x,
            metric_y=metric_y,
            source=source,  # type: ignore[arg-type]
            y_source=y_source,  # type: ignore[arg-type]
            align_by=align_by,  # type: ignore[arg-type]
            method=method,
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            nr_zona=nr_zona,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
        )

    @mcp.tool(
        name="series_compare",
        description=analytics_tools.series_compare.__doc__ or "Comparação YoY.",
    )
    def series_compare(
        metric: str,
        source: str = "detalhe",
        ano_eleicao: int | None = None,
        nr_turno: int | None = None,
        sg_uf: str | None = None,
        id_municipio: str | None = None,
        cd_municipio_tse: int | None = None,
        nr_zona: int | None = None,
        cd_cargo: int | None = None,
        sg_partido: str | None = None,
        max_rows: int | None = 50,
    ) -> dict[str, Any]:
        if source not in ("votacao", "detalhe"):
            raise ValueError("source deve ser 'votacao' ou 'detalhe'")
        return analytics_tools.series_compare(
            metric=metric,
            source=source,  # type: ignore[arg-type]
            ano_eleicao=ano_eleicao,
            nr_turno=nr_turno,
            sg_uf=sg_uf,
            id_municipio=id_municipio,
            cd_municipio_tse=cd_municipio_tse,
            nr_zona=nr_zona,
            cd_cargo=cd_cargo,
            sg_partido=sg_partido,
            max_rows=max_rows,
        )

    @mcp.tool(
        name="artifact_get",
        description=art_tools.artifact_get.__doc__ or "Lê artefato intermediário.",
    )
    def artifact_get(
        artifact_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        return art_tools.artifact_get(
            artifact_id=artifact_id, offset=offset, limit=limit
        )

    return mcp


def create_http_app():
    """ASGI app com Bearer auth (para uvicorn / testes)."""
    token = _mcp_token()
    db.ensure_schema()
    mcp = build_server()
    # host != localhost evita auto-enable de DNS rebinding só para 127.0.0.1
    bind_host = os.environ.get("HOST", "0.0.0.0")
    app = mcp.streamable_http_app(
        host=bind_host,
        transport_security=_transport_security(),
    )
    app.add_middleware(BearerAuthMiddleware, token=token)
    return app


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    # factory ensures middleware + schema init
    uvicorn.run(
        "ie_dados_mcp.server:create_http_app",
        factory=True,
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
