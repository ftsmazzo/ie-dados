-- ie-dados: extensões Postgres
-- Aplicar na Fase 1, antes das tabelas de referência.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- CREATE EXTENSION IF NOT EXISTS "postgis"; -- ativar só se precisarmos de geometria
