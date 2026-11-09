# Raw — Planos de Governo (TSE)

ZIPs/PDFs **não** entram no Git. Coloque cada ZIP em `AAAA/` (ou já extraído em `AAAA/pdf/`).

## Layout

```
data/raw/tse/planos_governo/
  2018/proposta_governo_2018_BR.zip
  2020/proposta_governo_2020_SP.zip   # um ZIP por UF (municipal)
  2022/proposta_governo_2022_BR.zip
  2022/proposta_governo_2022_SP.zip   # governadores por UF
  2024/proposta_governo_2024_SP.zip
  2026/proposta_governo_2026_BR.zip   # Presidente (atual = eleito 2026)
  2026/proposta_governo_2026_SP.zip   # Governador
```

Nome dos PDFs (padrão TSE): `{AAAA}{UF|BR}{sq_candidato}_{nn}.pdf`  
Ex.: `2026BR280002538811_01.pdf` → ano=2026, unidade=BR, `sq_candidato=280002538811`.

## P0 — anos e cargos

| Ano | Ciclo | Cargos típicos no pacote | CDN |
|-----|-------|--------------------------|-----|
| **2026** | Geral | Presidente (`_BR`) + Governador (`_UF`) | `proposta_governo_2026_BR.zip` / `_UF.zip` |
| 2024 | Municipal | Prefeito (`_UF`) | `proposta_governo_2024_{UF}.zip` |
| 2022 | Geral | Presidente + Governador | `proposta_governo_2022_BR.zip` / `_UF.zip` |
| 2020 | Municipal | Prefeito | `proposta_governo_2020_{UF}.zip` |
| 2018 | Geral | Presidente + Governador | `proposta_governo_2018_BR.zip` / `_UF.zip` |

Base URL:

`https://cdn.tse.jus.br/estatistica/sead/odsele/proposta_governo/proposta_governo_{AAAA}_{UF|BR}.zip`

Portais: [Candidatos 2026](https://dadosabertos.tse.jus.br/dataset/candidatos-2026) · [2024](https://dadosabertos.tse.jus.br/dataset/candidatos-2024) · [2022](https://dadosabertos.tse.jus.br/dataset/candidatos-2022)

## Prioridade de download

1. **2026_BR** (Presidente — mandato atual) — ~17 MB  
2. 2026_UF (Governadores) — dezenas de MB  
3. 2022_BR + 2018_BR (histórico Pres)  
4. 2024_UF / 2020_UF (Prefeitos; ZIPs grandes, ~0,3–1,4 GB/UF) — baixe por UF sob demanda  

UFs: AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO

## Pipeline

1. `scripts/inventario_planos_governo.py` — lista PDFs → CSV processado  
2. `scripts/load_planos_governo.py` — `ref.plano_governo` + flag `eleito` via `eleitoral`  
3. `scripts/index_planos_governo.py` — extract texto → chunks no acervo (`docs.plano_chunk`; eleitos primeiro, Pres 2026 no topo)

MCP: `plano_search_meta`, `plano_retrieve`, `plano_compare_tema`, `plano_seed_ideia`.
