# Schema — ie-dados

Schemas versionados em `sql/`.

## Convenções

- Identificador de município: `id_municipio` `CHAR(7)` (IBGE)
- UF: `sigla_uf` `CHAR(2)`
- Anos: `ano` `INTEGER`
- Timestamps de carga: `loaded_at TIMESTAMPTZ DEFAULT now()`
- Schema `ref`: referência geográfica/populacional
- Próximos: `eleitoral`, etc.

## Arquivos

| Arquivo | Domínio | Status |
|---------|---------|--------|
| `sql/000_extensions.sql` | extensões | ativo |
| `sql/001_ref_municipios.sql` | municípios + população | ativo em produção |

## Tabelas ativas

### `ref.municipio`

PK `id_municipio`. Inclui UF, regiões geográficas intermediária/imediata (DTB 2025).

### `ref.populacao_municipio`

PK (`id_municipio`, `ano`). FK para `ref.municipio`. Estimativa IBGE 2024 (referência 01/07/2024).
