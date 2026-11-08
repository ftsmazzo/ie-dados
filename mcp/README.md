# MCP ie-dados

Servidor MCP tipado sobre o Postgres `iedados`. Sem SQL livre. Consultas grandes viram artefato no servidor.

## Fluxo recomendado (agentes)

1. `list_domains` — o que existe  
2. `describe_domain` — campos de um domínio  
3. `resolve_municipio` — obter `id_municipio`  
4. `election_estimate` — quantos grupos a agregação gera  
5. `election_aggregate` — resultado inline ou `artifact_id`  
6. `artifact_get` — paginar artefato grande  

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
| election_estimate | cheap | antes de agregações amplas |
| election_aggregate | heavy | `group_by` + `metrics` obrigatórios |
| artifact_get | cheap | só com `artifact_id` válido |

## Limites anti-token

- `max_rows` default 50, hard cap 200  
- agregação obrigatória em votação  
- escopo mínimo: `ano_eleicao` e/ou `id_municipio` e/ou `sg_uf`  
- se muitos grupos → `mode=artifact` + amostra de 5 linhas  

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
