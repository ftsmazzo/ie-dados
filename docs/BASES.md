# Catálogo de bases — ie-dados

Status possíveis: `aguardando ZIP` | `ZIP recebido` | `schema ok` | `carregada` | `validada` | `pronta`

Legado (`inteligencia-eleitoral*`, Postgres `iebrasil`, etc.): **fora de escopo**. Não migrar.

## Fila

| # | Domínio | Pasta raw | Fonte | Chave(s) | Status |
|---|---------|-----------|-------|----------|--------|
| 1 | Municípios + população | `data/raw/ibge/municipios/` e `data/raw/ibge/populacao/` | IBGE | `id_municipio` (7 dígitos) | **pronta** |
| 2 | Urnas / resultados | `data/raw/tse/urna/` | TSE | `id_municipio` + `zona` (+ ano/turno/cargo) | **aguardando ZIP (onda 1: 2022+2024)** |
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

## Base 2 — Urnas / município + zona (em andamento)

- **Objetivo:** resultados oficiais com granularidade **município + zona eleitoral**, cruzáveis com `ref.municipio`
- **Não usamos nesta onda:** Boletim de Urna (máquina a máquina) nem seção — vêm depois, se precisar
- **Onda 1:** eleições **2022** (geral) e **2024** (municipal)
- **Arquivos-chave por ano:**
  1. `votacao_candidato_munzona` — votos nominais por município/zona/candidato/cargo/turno
  2. `detalhe_votacao_munzona` — aptos, comparecimento, brancos, nulos por município/zona

### Downloads oficiais (você baixa e coloca nas pastas)

Portais:
- [Resultados 2022](https://dadosabertos.tse.jus.br/dataset/resultados-2022)
- [Resultados 2024](https://dadosabertos.tse.jus.br/dataset/resultados-2024)

Links diretos CDN:

| Ano | Arquivo | Link | Pasta |
|-----|---------|------|-------|
| 2022 | Votação nominal mun/zona | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2022.zip | `data/raw/tse/urna/2022/votacao_candidato_munzona/` |
| 2022 | Detalhe apuração mun/zona | https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip | `data/raw/tse/urna/2022/detalhe_votacao_munzona/` |
| 2024 | Votação nominal mun/zona | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2024.zip | `data/raw/tse/urna/2024/votacao_candidato_munzona/` |
| 2024 | Detalhe apuração mun/zona | https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2024.zip | `data/raw/tse/urna/2024/detalhe_votacao_munzona/` |

Arquivos grandes (centenas de MB a alguns GB). Não precisa abrir no Excel.

### Depois dos ZIPs (nós)

1. Mapear `CD_MUNICIPIO` (código TSE) → `id_municipio` IBGE (FK para Base 1)
2. DDL em schema `eleitoral`
3. Carga + validação (totais por UF/cargo vs. divulgação TSE)
4. Só então marcar Base 2 como `pronta` e falar de 2018/2020 ou seção

## Notas

- ZIPs nunca entram no Git.
- Onda 1 = 2022 + 2024. Histórico antigo sob demanda.
