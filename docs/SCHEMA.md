# Schema — ie-dados

Schemas versionados em `sql/`.

## Convenções

- Identificador IBGE: `id_municipio` `CHAR(7)`
- Código TSE do município: `cd_municipio_tse` `INTEGER`
- UF: `sigla_uf` / `sg_uf` `CHAR(2)`
- Schema `ref`: referência geográfica/populacional + cruzamentos
- Schema `eleitoral`: resultados município + zona

## Arquivos

| Arquivo | Domínio | Status |
|---------|---------|--------|
| `sql/000_extensions.sql` | extensões | ativo |
| `sql/001_ref_municipios.sql` | municípios + população | ativo |
| `sql/002_eleitoral.sql` | cruzamento TSE/IBGE + detalhe + votação | ativo |
| `sql/003_mcp.sql` | artefatos MCP | ativo |
| `sql/004_financeiro.sql` | prestação candidatos (receitas/despesas) | ativo |

## Tabelas

### `ref.municipio` / `ref.populacao_municipio`
Base 1 (IBGE).

### `ref.municipio_tse`
Cruzamento oficial `CD_MUNICIPIO_TSE` → `id_municipio` IBGE.

### `eleitoral.detalhe_munzona`
Aptos, comparecimento, brancos, nulos por município/zona/cargo/turno/ano.

### `eleitoral.votacao_candidato_munzona`
Votos nominais (particionada por `ano_eleicao`, 1998–2026).
Colunas essenciais: município TSE/IBGE, zona, cargo, candidato, partido, votos, situação.

### `financeiro.receita_candidato` / `financeiro.despesa_contratada_candidato`
Base 3 (prestação TSE, particionadas por `ano_eleicao`).  
Chave de ligação com Base 2: `sq_candidato` + `ano_eleicao`.  
`id_municipio` preenchido quando `SG_UE` é código TSE municipal (eleições locais); em gerais costuma ser nulo (UE = UF).
