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
| mun_list | cheap | municípios no Acervo Municípios |
| mun_list_secretarias | cheap | secretarias de um município |
| mun_get_secretaria | cheap | ficha + trechos de uma secretaria |
| mun_retrieve | medium | FTS institucional (exige município) |
| mun_search_servico | medium | atalho FTS tipo=servico |
| plano_search_meta | cheap | catálogo planos TSE; filtro `eleito` / cargo / ano |
| plano_retrieve | medium | FTS no acervo (trechos + citação) |
| plano_compare_tema | medium | mesmo tema em N planos (default só eleitos) |
| plano_seed_ideia | medium | esqueleto a partir de eleitos; default Pres 2026 |
| election_estimate | cheap | antes de agregações amplas |
| election_aggregate | heavy | `group_by` + `metrics` obrigatórios |
| finance_estimate | cheap | antes de agregações de receita/despesa |
| finance_aggregate | heavy | `source=receita\|despesa\|paga\|doador` |
| finance_pago_contratado | heavy | taxa pago÷contratado (join `sq_despesa`) |
| series_build | medium | série temporal (exige `ano_eleicao` no group_by) |
| correlate | medium | Pearson/Spearman; `y_source=metric\|populacao\|pib\|idhm`; `align_by=ano\|municipio` |
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

### Exemplo — planos de governo (Base 5 / Acervo)

1. `plano_search_meta` `ano_eleicao=2026`, `cd_cargo=1`, `eleito=true` → Presidente atual  
2. `plano_retrieve` `query="educação"`, mesmos filtros → trechos com citação  
3. `plano_compare_tema` / `plano_seed_ideia` `tema="saúde"` (default Pres 2026 eleito)  
4. Opcional: `get_pib` / `get_idhm` no município-alvo para contextualizar

### Exemplo — Acervo Municípios (Base 6 / Ribeirão Preto)

1. `mun_list` → municípios no acervo  
2. `mun_list_secretarias` `slug_municipio=ribeirao-preto` (ou `id_municipio=3543402`)  
3. `mun_get_secretaria` `secretaria_slug=saude` + mesmo escopo → ficha + trechos  
4. `mun_retrieve` `query="UBS"` / `mun_search_servico` `query="IPTU"` — sempre com município

### Exemplo — abstencão × PIB / IDHM (Base 4)

**Série temporal (um município × anos)** — só PIB (IDHM tem só 3 censos):

1. `resolve_municipio` → `3509502`
2. `correlate` `metric_x=rate_abstencao`, `y_source=pib`, `metric_y=pib_per_capita`,  
   `align_by=ano`, `id_municipio`, `cd_cargo=13`, `nr_turno=1`

**Corte transversal (municípios de uma UF no ano)** — PIB ou IDHM:

1. `correlate` `metric_x=rate_abstencao`, `y_source=idhm`, `metric_y=idhm`,  
   `align_by=municipio`, `ano_eleicao=2020`, `sg_uf=SP`, `cd_cargo=13`, `nr_turno=1`  
   (IDHM usa censo mais próximo → 2010)
2. Idem com `y_source=pib`, `metric_y=pib_per_capita` (PIB do próprio `ano_eleicao`)

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
