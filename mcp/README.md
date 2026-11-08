# MCP ie-dados

Servidor MCP tipado sobre o Postgres `iedados`. Sem SQL livre. Consultas grandes viram artefato no servidor.

## Fluxo recomendado (agentes)

1. `list_domains` — o que existe  
2. `describe_domain` — campos de um domínio  
3. `resolve_municipio` — obter `id_municipio`  
4. `election_estimate` — quantos grupos a agregação gera  
5. `election_aggregate` — resultado inline ou `artifact_id`  
6. **Analytics:** `series_build` → `correlate` / `series_compare`  
7. `artifact_get` — paginar artefato grande  

## Auth

Header: `Authorization: Bearer <MCP_TOKEN>`

Rotas públicas: `GET /health`, `GET /health/ready`  
MCP endpoint: `POST /mcp` (streamable HTTP)

## Tools

| Tool | Custo | Notas |
|------|-------|-------|
| list_domains | cheap | início de sessão |
| describe_domain | cheap | um domínio por vez |
| resolve_municipio | cheap | nome/UF/código |
| get_populacao | cheap | exige município ou UF |
| get_pib | cheap | PIB municipal IBGE; exige município ou UF; ano 2010–2023 |
| get_idhm | cheap | IDHM Atlas; exige município ou UF; ano 1991/2000/2010 |
| election_estimate | cheap | antes de agregações amplas |
| election_aggregate | heavy | `group_by` + `metrics` obrigatórios |
| finance_estimate | cheap | antes de agregações de receita/despesa |
| finance_aggregate | heavy | `source=receita\|despesa\|paga\|doador` |
| finance_pago_contratado | heavy | taxa pago÷contratado (join `sq_despesa`) |
| series_build | medium | série temporal (exige `ano_eleicao` no group_by) |
| correlate | medium | Pearson/Spearman; resumo + amostra |
| series_compare | medium | delta e % YoY |
| artifact_get | cheap | só com `artifact_id` válido |

## Limites anti-token

- `max_rows` default 50, hard cap 200  
- agregação obrigatória em votação  
- escopo mínimo: `ano_eleicao` e/ou `id_municipio` e/ou `sg_uf`  
- se muitos grupos → `mode=artifact` + amostra de 5 linhas  
- `correlate` exige ≥ 5 pontos alinhados por ano  

## Local

```bash
cd mcp
pip install -r requirements.txt
set PYTHONPATH=src
set DATABASE_URL=postgresql://iedados:...@host:5432/iedados
set MCP_TOKEN=seu-token
python -m ie_dados_mcp.server
```

## Produção

App EasyPanel `ie-dados` / serviço `mcp`, build a partir de `/mcp` no repo.

- URL: `https://ie-dados-mcp.kxryyk.easypanel.host`
- Health: `GET /health` (público)
- MCP: `POST /mcp` com `Authorization: Bearer <MCP_TOKEN>`
- Opcional: `MCP_ALLOWED_HOSTS=ie-dados-mcp.kxryyk.easypanel.host` para reativar checagem de Host

### Exemplo — votos por partido (Campinas / Dep. Estadual 2022)

1. `resolve_municipio` com `nome=Campinas`, `sigla_uf=SP` → `id_municipio=3509502`
2. `election_estimate` com `ano_eleicao=2022`, `nr_turno=1`, `cd_cargo=7`, `id_municipio`, `group_by=["nr_partido"]`, `metrics=["sum_votos"]`
3. `election_aggregate` com os mesmos filtros (`max_rows` ≤ 200)

Metrics votação: `sum_votos`, `sum_votos_validos`, `n_linhas`.

### Exemplo — nulos vs válidos ao longo dos anos (analytics)

1. `resolve_municipio` → `3509502`
2. `series_build` com `source=detalhe`, `id_municipio`, `cd_cargo=13` (ou `7`), `nr_turno=1`,  
   `metrics=["sum_nulos","sum_validos","rate_nulos_sobre_validos"]`
3. `correlate` com `metric_x=rate_nulos_sobre_validos`, `metric_y=sum_validos`, mesmos filtros  
   — ou `metric_y=populacao`, `y_source=populacao`
4. `series_compare` com `metric=rate_nulos_sobre_validos` para deltas YoY

Rates em `detalhe`: `rate_nulos_sobre_validos`, `rate_brancos_sobre_validos`, `rate_abstencao`, `rate_comparecimento`.

### Exemplo — receita por partido (Campinas / vereador 2024)

1. `resolve_municipio` → `3509502`
2. `finance_estimate` `source=receita`, `ano_eleicao=2024`, `id_municipio`, `cd_cargo=13`, `group_by=["sg_partido"]`, `metrics=["sum_receita"]`
3. `finance_aggregate` com os mesmos filtros

Metrics: `sum_receita` / `sum_despesa` / `sum_pagto`, `n_linhas`, `n_candidatos`, `n_doadores`.  
`source`: `receita` | `despesa` | `paga` | `doador` (paga/doador: filtre por `ano_eleicao` e/ou `sg_uf`).  
`finance_pago_contratado`: `sum_contratada`, `sum_pago`, `rate_pago_sobre_contratado` — melhor em 2020/2024 com `id_municipio`.  
Anos P0: 2018, 2020, 2022, 2024, 2026.

`cd_cargo` comuns: `1` Presidente, `3` Governador, `5` Senador, `6` Dep. Federal, `7` Dep. Estadual, `11` Prefeito, `13` Vereador.
