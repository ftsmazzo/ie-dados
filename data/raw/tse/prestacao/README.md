# Raw — Prestação de contas (TSE)

ZIPs **não** entram no Git. Coloque cada arquivo na pasta do ano.

## Layout

```
data/raw/tse/prestacao/
  AAAA/candidatos/<arquivo.zip>   # preferencial
  AAAA/<arquivo.zip>              # aceito pelo loader
```

Loader: `scripts/load_prestacao.py` → schema `financeiro` (`sql/004_financeiro.sql`).  
Usa CSVs por UF; ignora `*_BRASIL.csv` / `*_BR.csv` (evita duplicar).

## Prioridade

| Lote | Anos | Formato CDN |
|------|------|-------------|
| **P0** | 2026, 2024, 2022, 2020, 2018 | `prestacao_de_contas_eleitorais_candidatos_AAAA.zip` |
| P1 | 2016, 2012 | `prestacao_contas_final_AAAA.zip` |
| P2 | 2010, 2008, 2004, 2002 | `prestacao_contas_AAAA.zip` |

Comece pelo **P0**. Avisando que o lote está nas pastas, seguimos schema + carga.
