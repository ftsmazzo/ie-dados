# Smoke — recorte P0 (Ribeirão Preto)

Roteiro completo e frases proibidas: **`RECORTE-P0-PERGUNTAS.md`**.

| # | Pergunta | Tool | OK se… |
|---|----------|------|--------|
| 1 | “O que é a CABS e como agendo?” | `mun_search_servico` “CABS” | CadÚnico + Prudente de Morais 457 + (16) 3605-2800 |
| 2 | “Telefone da Saúde e do Prefeito” | `mun_get_secretaria` / retrieve | 3977-9300 e 3977-9000 |
| 3 | “Onde atendo Fazenda/IPTU presencial?” | `mun_get_secretaria` `fazenda` | Poupatempo Kennedy 1500 + horário |
| 4 | “Quais CRAS existem? Me dá o da região Central.” | `mun_search_servico` “CRAS” | CRAS 1 Rua São José 223 |
| 5 | “PIB per capita de Ribeirão” | `get_pib` | número + ano |

## Se falhar

1. Health MCP `ok`
2. Token / Claude Desktop reiniciado
3. Conferir que a carga P0 rodou (`n_docs` ≈ 8, não 37 do scrape bruto)
