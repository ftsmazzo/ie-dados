# Smoke — 5 perguntas de aceite (Ribeirão Preto)

Rodar com o MCP `ie-dados` conectado e a persona colada. Esperado: resposta com dados reais + menção da tool.

| # | Pergunta (falar / digitar) | Tool esperada | OK se… |
|---|----------------------------|---------------|--------|
| 1 | “Quais secretarias temos no acervo de Ribeirão?” | `mun_list_secretarias` | Lista inclui Saúde, Fazenda, Educação |
| 2 | “Me dá a ficha da Secretaria da Saúde.” | `mun_get_secretaria` (`saude`) | Título + trechos / contatos da base |
| 3 | “Como faço sobre IPTU?” | `mun_search_servico` | Hits de Fazenda/serviço com citação |
| 4 | “Qual o PIB per capita de Ribeirão no ano mais recente?” | `resolve_municipio` + `get_pib` | Número com ano |
| 5 | “No último ciclo municipal, quem liderou votos a prefeito em Ribeirão?” (ajustar ano se preciso: 2024) | `election_estimate` → `election_aggregate` | Ranking com votos, escopo município |

## Extras (demo opcional)

- “Compara abstencão e PIB em Ribeirão ao longo dos anos.” → `correlate` / `series_build`
- “O que o plano do presidente eleito em 2026 diz sobre saúde?” → `plano_retrieve` (`eleito=true`, `cd_cargo=1`)

## Se falhar

1. `GET https://ie-dados-mcp.kxryyk.easypanel.host/health` → precisa ser `ok`
2. Conferir Bearer no `mcp.json` (sem espaço a mais, `Bearer ` + token)
3. Reiniciar Claude Code / Cursor
4. Pedir `list_domains` — se não listar `municipios` / tools `mun_*`, o deploy MCP está velho ou o token está errado
