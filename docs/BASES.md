# Catálogo de bases — ie-dados

Status possíveis: `aguardando ZIP` | `ZIP recebido` | `schema ok` | `carregada` | `validada` | `pronta`

Legado (`inteligencia-eleitoral*`, Postgres `iebrasil`, etc.): **fora de escopo**. Não migrar.

## Fila

| # | Domínio | Pasta raw | Fonte | Chave(s) | Status |
|---|---------|-----------|-------|----------|--------|
| 1 | Municípios + população | `data/raw/ibge/municipios/` e `data/raw/ibge/populacao/` | IBGE | `id_municipio` (7 dígitos) | **pronta** |
| 2 | Urnas / resultados | `data/raw/tse/urna/` | TSE | `id_municipio` + `zona` (+ ano/turno/cargo) | **pronta** |
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

## Base 2 — Urnas / município + zona (pronta)

- **Objetivo:** série temporal longa para estudar **alternância**, tempo de partido no poder e padrões territoriais, com granularidade **município + zona**
- **Tabelas:** `ref.municipio_tse`, `eleitoral.detalhe_munzona`, `eleitoral.votacao_candidato_munzona` (particionada por ano)
- **Scripts:** `scripts/load_eleitoral.py` · **SQL:** `sql/002_eleitoral.sql`
- **Não nesta base ainda:** Boletim de Urna (máquina) nem seção; classificação ideológica esquerda/direita (camada curada depois)

### Validação (carga em produção)

| Checagem | Resultado |
|----------|-----------|
| Cruzamento TSE↔IBGE | 5.571 (0 sem `ref.municipio`) |
| Detalhe mun/zona | 306.435 |
| Detalhe sem IBGE | 4 (casos especiais / exterior) |
| Votação candidato mun/zona | **45.317.438** |
| Votação sem IBGE | 60 |
| Anos na votação | **15** (1998–2026) |
| Inventário ZIP raw | 30/30 |

### Escopo temporal (verificado no CDN)

**Eleições gerais** (Presidente, Governador, Senado, Deputados):  
`1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026`

**Eleições municipais** (Prefeito, Vereador):  
`2000, 2004, 2008, 2012, 2016, 2020, 2024`

Isso cobre ~28 anos (1998→2026) — lastro adequado para alternância nacional e local.

Por ano, 2 arquivos:

1. `votacao_candidato_munzona_AAAA.zip` — votos nominais
2. `detalhe_votacao_munzona_AAAA.zip` — aptos / comparecimento / brancos / nulos

Pasta: `data/raw/tse/urna/AAAA/<tipo>/`

URL padrão:

```
https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_AAAA.zip
https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_AAAA.zip
```

### Prioridade de download (para não travar)

| Prioridade | Anos | Motivo |
|------------|------|--------|
| P0 | **2026**, 2022, 2018, 2014 | ciclo recente + 2026 fechada |
| P1 | 2010, 2006, 2002, 1998 | série geral completa (alternância Presidência/Congresso) |
| P2 | 2024, 2020, 2016, 2012, 2008, 2004, 2000 | poder local (prefeituras) |

Links 2026 (confirmar na pasta):

| Arquivo | Link | Pasta |
|---------|------|-------|
| Votação 2026 | https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2026.zip | `data/raw/tse/urna/2026/votacao_candidato_munzona/` |
| Detalhe 2026 | https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip | `data/raw/tse/urna/2026/detalhe_votacao_munzona/` |

Portal: [Resultados 2026](https://dadosabertos.tse.jus.br/pt_BR/dataset/resultados-2026)

Obs.: anos antigos (pré-2014) têm menos colunas / qualidade irregular — carregamos com o mesmo schema e flag de qualidade por ano.

### Depois dos ZIPs (nós)

1. Mapa `CD_MUNICIPIO` TSE → `id_municipio` IBGE
2. Schema `eleitoral` (votos + detalhe + metadados de eleição)
3. Carga por ano + validação de totais
4. Camada analítica futura: eixo ideológico / coalizão (tabela curada, separada do fato TSE)

## Notas

- ZIPs nunca entram no Git.
- Pode baixar por prioridade (P0 → P1 → P2); avisando a cada lote já dá para ir carregando.
