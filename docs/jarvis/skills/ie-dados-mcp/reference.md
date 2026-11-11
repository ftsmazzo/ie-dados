# Referência rápida — ie-dados MCP

## Domínios (`list_domains` / `describe_domain`)

| id | Uso |
|----|-----|
| `ref` | município, população, PIB, IDHM |
| `eleitoral` | urnas / votação |
| `financeiro` | prestação de contas |
| `municipios` | acervo institucional (Ribeirão P0) |
| `planos` | planos de governo TSE |

## Tools por custo

**cheap:** `list_domains`, `describe_domain`, `resolve_municipio`, `get_populacao`, `get_pib`, `get_idhm`, `mun_list`, `mun_list_secretarias`, `mun_get_secretaria`, `plano_search_meta`, `election_estimate`, `finance_estimate`, `artifact_get`

**medium:** `mun_retrieve`, `mun_search_servico`, `plano_retrieve`, `plano_compare_tema`, `plano_seed_ideia`, `series_build`, `correlate`, `series_compare`

**heavy:** `election_aggregate`, `finance_aggregate`, `finance_pago_contratado`

## Limites anti-token

- `max_rows` default ~50, hard cap ~200
- Agregação obrigatória em votação
- Escopo mínimo: `ano_eleicao` e/ou `id_municipio` e/ou `sg_uf`
- `correlate` precisa ≥ 5 pontos alinhados

## P0 vs scrape bruto

FTS ativo = recorte curado (~8 docs). Pasta `_scrape_bruto/` no repo **não** está indexada. Ampliação = nova curadoria + `load_acervo_municipio.py`.
