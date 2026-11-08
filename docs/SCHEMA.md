# Schema — ie-dados

Schemas versionados em `sql/`. Conteúdo DDL real entra na Fase 1 (após ZIPs da base de municípios).

## Convenções

- Identificador de município: `id_municipio` `CHAR(7)` (IBGE)
- UF: `sigla_uf` `CHAR(2)`
- Anos: `ano` `INTEGER`
- Timestamps de carga: `loaded_at TIMESTAMPTZ DEFAULT now()`
- Schema Postgres inicial: `ref` (referência geográfica/populacional), depois `eleitoral`, etc.

## Arquivos

| Arquivo | Domínio | Status |
|---------|---------|--------|
| `sql/000_extensions.sql` | extensões | placeholder |
| `sql/001_ref_municipios.sql` | municípios + população | placeholder (Fase 1) |
