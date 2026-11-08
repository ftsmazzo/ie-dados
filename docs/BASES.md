# Catálogo de bases — ie-dados

Status possíveis: `aguardando ZIP` | `ZIP recebido` | `schema ok` | `carregada` | `validada` | `pronta`

Legado (`inteligencia-eleitoral*`, Postgres `iebrasil`, etc.): **fora de escopo**. Não migrar.

## Fila

| # | Domínio | Pasta raw | Fonte | Chave(s) | Status |
|---|---------|-----------|-------|----------|--------|
| 1 | Municípios + população | `data/raw/ibge/municipios/` e `data/raw/ibge/populacao/` | IBGE | `id_municipio` (7 dígitos) | **pronta** |
| 2 | Urnas / resultados | `data/raw/tse/urna/` | TSE | `id_municipio` + `zona` (+ ano/turno/cargo) | **pronta** |
| 3 | Financiamento / prestação | `data/raw/tse/prestacao/` | TSE ASEPA | `sq_candidato` + `ano` (+ município quando houver) | **pronta (P0)** |
| 4 | Indicadores socioeconômicos | `data/raw/ibge/pib_municipios/` + `data/raw/atlas/idhm/` | IBGE + Atlas/PNUD | `id_municipio` + `ano` | **carregado P0** (`ref.pib_municipio` 77.965 / `ref.idhm_municipio` 16.643) |
| 5 | Senado / leis | `data/raw/congresso/` | fontes oficiais | a definir | aguardando ZIP |

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

## Base 3 — Financiamento / prestação de contas (**P0 pronta**)

- **Objetivo:** receitas e despesas de campanha para cruzar **dinheiro × voto × porte municipal**
- **Pasta:** `data/raw/tse/prestacao/AAAA/candidatos/`
- **Tabelas:** `financeiro.receita_candidato`, `financeiro.despesa_contratada_candidato`
- **Scripts:** `scripts/load_prestacao.py` · **SQL:** `sql/004_financeiro.sql`
- **MCP:** `finance_estimate` / `finance_aggregate` (domínio `financeiro`)
- **Chave com Base 2:** `sq_candidato` + `ano_eleicao`
- **Extensão P0:** `despesa_paga_candidato`, `receita_doador_originario` (`sql/005_financeiro_ext.sql`)
- **Fora do P0 ainda:** órgãos partidários, extratos, anos P1/P2

### Validação (carga P0 em produção)

| Ano | Receitas | c/ IBGE | Despesas contr. | c/ IBGE |
|-----|----------|---------|-----------------|---------|
| 2018 | 328.657 | 0 (geral) | 1.716.410 | 0 |
| 2020 | 2.339.074 | 100% | 4.107.530 | 100% |
| 2022 | 281.928 | 0 (geral) | 2.200.603 | 0 |
| 2024 | 2.041.143 | 100% | 4.453.427 | 100% |
| 2026 | 249.203 | 0 (geral) | 1.768.051 | 0 |
| **Total** | **5.240.005** | | **14.246.021** | |

| Tabela extensão | Linhas | Soma R$ |
|-----------------|--------|---------|
| `despesa_paga_candidato` | **12.830.799** | ~24,3 bi |
| `receita_doador_originario` | **1.632.819** | ~0,77 bi |

Smoke: Campinas 2024 vereador → 4.001 receitas / R$ 15,3 mi.  
Join 2022 receita↔votação: 26.056 / 27.945 `sq_candidato` com voto.  
MCP: `finance_aggregate` com `source=receita|despesa|paga|doador`.

### Prioridade de download

| Lote | Anos | Motivo |
|------|------|--------|
| **P0** | 2026, 2024, 2022, 2020, 2018 | ciclo recente + mesmo padrão de nome no CDN |
| P1 | 2016, 2014, 2012 | municipais/gerais intermediários (nome de arquivo muda) |
| P2 | 2010, 2008, 2004, 2002 | série antiga (schema mais irregular) |

### P0 — baixar agora (link → pasta)

Raiz do projeto: `C:\Users\anjo_\OneDrive\Projetos-FabriaIA\ie-dados\`

| Ano | Link | Pasta (coloque o ZIP aqui) | ~tamanho |
|-----|------|----------------------------|----------|
| 2026 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip | `data/raw/tse/prestacao/2026/candidatos/` | ~402 MB |
| 2024 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip | `data/raw/tse/prestacao/2024/candidatos/` | ~1,2 GB |
| 2022 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip | `data/raw/tse/prestacao/2022/candidatos/` | ~497 MB |
| 2020 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2020.zip | `data/raw/tse/prestacao/2020/candidatos/` | ~1,3 GB |
| 2018 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2018.zip | `data/raw/tse/prestacao/2018/candidatos/` | ~297 MB |

Portais: [2026](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026) · [2024](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2024) · [2022](https://dadosabertos.tse.jus.br/dataset/dadosabertos-tse-jus-br-dataset-prestacao-de-contas-eleitorais-2022)

### P1 / P2 (só depois do P0 — nomes diferentes)

| Ano | Arquivo CDN | Pasta |
|-----|-------------|-------|
| 2016 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_contas_final_2016.zip | `data/raw/tse/prestacao/2016/candidatos/` |
| 2014 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_final_2014.zip | `data/raw/tse/prestacao/2014/candidatos/` |
| 2012 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_contas_final_2012.zip | `data/raw/tse/prestacao/2012/candidatos/` |
| 2010 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_contas_2010.zip | `data/raw/tse/prestacao/2010/candidatos/` |
| 2008 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_contas_2008.zip | `data/raw/tse/prestacao/2008/candidatos/` |
| 2004 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_contas_2004.zip | `data/raw/tse/prestacao/2004/candidatos/` |
| 2002 | https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_contas_2002.zip | `data/raw/tse/prestacao/2002/candidatos/` |

### Depois dos ZIPs (nós)

1. Inventariar CSVs dentro do ZIP (receitas / despesas / …)
2. Schema `financeiro` (ou `eleitoral` + tabelas de prestação) + ligar a `sq_candidato` / município
3. Carga + validação de totais
4. Tools MCP `finance_estimate` / `finance_aggregate` (mesmo padrão anti-token)

## Base 4 — Indicadores socioeconômicos municipais (em andamento)

- **Objetivo:** cruzar **voto × dinheiro × desenvolvimento** no mesmo `id_municipio`
- **Tabelas previstas:** `ref.pib_municipio`, `ref.idhm_municipio` (schema depois do inventário)
- **MCP previsto:** métricas em `get_indicadores` / `correlate` com PIB per capita e IDHM
- **Fora do P0:** SIDRA automático, indicadores anuais extras do Atlas, Senado

### P0 — baixar agora (link → pasta)

Raiz: `C:\Users\anjo_\OneDrive\Projetos-FabriaIA\ie-dados\`

| # | O quê | Link | Pasta | ~tam. |
|---|--------|------|-------|-------|
| **1 (obrigatório)** | PIB municipal IBGE 2010–2023 (TXT) | https://ftp.ibge.gov.br/Pib_Municipios/2022_2023/base/base_de_dados_2010_2023_txt.zip | `data/raw/ibge/pib_municipios/` | ~7,4 MB |
| 1b (opcional) | mesma base em XLSX | https://ftp.ibge.gov.br/Pib_Municipios/2022_2023/base/base_de_dados_2010_2023_xlsx.zip | `data/raw/ibge/pib_municipios/` | ~20 MB |
| **2 (obrigatório)** | IDHM municipal | Espelhos CSV em `data/raw/atlas/idhm/` (biblioteca Atlas e OneDrive dados.gov falham; ver README da pasta). Oficial opcional: [dados.gov.br/Atlas](https://dados.gov.br/dados/conjuntos-dados/atlasbrasil) → **Censo Demográfico (1991, 2000 e 2010)** | `data/raw/atlas/idhm/` | ~1 MB CSV |

Portal PIB: [IBGE — PIB dos Municípios](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html)

### Status P0 (feito)

1. Inventário + `sql/006_socioeconomico.sql`
2. `scripts/prepare_socioeconomico.py` + `scripts/load_socioeconomico.py`
3. Validação: PIB 2010–2023 (5.570 mun em 2023); IDHM 2010=5.565 / 2000=5.539 / 1991=5.539; órfãos=0
4. **Próximo:** MCP métricas `get_indicadores` / `correlate` com PIB per capita e IDHM

## Notas

- ZIPs nunca entram no Git.
- Pode baixar por prioridade (P0 → P1 → P2); avisando a cada lote já dá para ir carregando.
