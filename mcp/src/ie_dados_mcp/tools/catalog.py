from __future__ import annotations

from ie_dados_mcp import catalog as cat


def list_domains() -> dict:
    """Lista domínios de dados disponíveis (ref, eleitoral, ...).

    WHEN TO USE: primeiro passo de qualquer sessão — descobrir o que existe.
    WHEN NOT TO USE: se já sabe o domínio; vá direto para describe_domain.
    COST: cheap.
    """
    return {
        "domains": cat.list_domains(),
        "flow": (
            "list_domains → describe_domain → resolve_municipio → "
            "election_estimate → election_aggregate (ou artifact_get)"
        ),
    }


def describe_domain(domain_id: str) -> dict:
    """Detalha tabelas, campos e chaves de UM domínio.

    WHEN TO USE: depois de list_domains, antes de montar filtros.
    WHEN NOT TO USE: não peça vários domínios de uma vez — um por chamada.
    COST: cheap.
    """
    return cat.describe_domain(domain_id)
