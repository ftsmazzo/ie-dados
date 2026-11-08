-- ie-dados: schema de municípios + população
-- PLACEHOLDER — DDL definitivo após receber os ZIPs oficiais do IBGE (Fase 1).
--
-- Esperado:
--   CREATE SCHEMA IF NOT EXISTS ref;
--   ref.municipio (id_municipio CHAR(7) PK, nome, sigla_uf, ...)
--   ref.populacao_municipio (id_municipio, ano, populacao, fonte, ...)

-- SELECT '001_ref_municipios: aguardando ZIP' AS status;
