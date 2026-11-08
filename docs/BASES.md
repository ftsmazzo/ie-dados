# Catálogo de bases — ie-dados

Status possíveis: `aguardando ZIP` | `ZIP recebido` | `schema ok` | `carregada` | `validada` | `pronta`

Legado (`inteligencia-eleitoral*`, Postgres `iebrasil`, etc.): **fora de escopo**. Não migrar.

## Fila

| # | Domínio | Pasta raw | Fonte | Chave(s) | Status |
|---|---------|-----------|-------|----------|--------|
| 1 | Municípios + população | `data/raw/ibge/municipios/` e `data/raw/ibge/populacao/` | IBGE | `id_municipio` (7 dígitos) | **pronta** |
| 2 | Urnas / resultados | `data/raw/tse/urna/` | TSE | `id_municipio` + `zona` (+ ano/turno/cargo) | aguardando ZIP |
| 3 | Financiamento / dinheiro | `data/raw/tse/prestacao/` | TSE | a definir com base 1–2 | aguardando ZIP |
| 4 | Senado / leis | `data/raw/congresso/` | fontes oficiais | a definir | aguardando ZIP |

## Base 1 — Municípios + população (pronta)

- **Objetivo:** diretório canônico de municípios brasileiros + população estimada 2024
- **Chave:** `id_municipio` CHAR(7) IBGE
- **Tabelas:** `ref.municipio`, `ref.populacao_municipio`
- **Scripts:** `scripts/prepare_ref_ibge.py`, `scripts/load_ref_ibge.py`
- **SQL:** `sql/000_extensions.sql`, `sql/001_ref_municipios.sql`

### Fontes usadas

| Arquivo | Pasta | Origem |
|---------|-------|--------|
| `DTB_2025.zip` → `RELATORIO_DTB_BRASIL_2025_MUNICIPIOS.xls` | `data/raw/ibge/municipios/` | [geoftp DTB 2025](https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/DTB_2025.zip) |
| `POP2024_20241230.xls` | `data/raw/ibge/populacao/` | [FTP Estimativas 2024](https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2024/POP2024_20241230.xls) |

### Validação (carga em produção)

| Checagem | Resultado |
|----------|-----------|
| Municípios | 5.571 |
| Linhas população 2024 | 5.571 |
| Municípios sem população 2024 | 0 |
| UFs distintas | 27 |
| Soma população Brasil | 212.583.750 (bate com total IBGE da planilha) |
| População mínima | 854 (> 0) |
| Chaves DTB ∩ população | 100% |

## Base 2 — Urnas (próxima, ainda não)

Quando a Base 1 estiver estável (já está), combinamos os ZIPs do TSE com granularidade município + zona.

## Notas

- ZIPs nunca entram no Git.
- Só avançamos para a base 2 após alinharmos juntos o recorte (anos/cargos).
