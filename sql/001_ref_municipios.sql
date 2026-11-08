-- ie-dados: referência geográfica e população municipal
-- Fontes: IBGE DTB 2025 + Estimativas POP2024_20241230

CREATE SCHEMA IF NOT EXISTS ref;

CREATE TABLE IF NOT EXISTS ref.municipio (
    id_municipio              CHAR(7) PRIMARY KEY,
    nome                      TEXT NOT NULL,
    sigla_uf                  CHAR(2) NOT NULL,
    codigo_uf                 CHAR(2) NOT NULL,
    nome_uf                   TEXT NOT NULL,
    id_regiao_intermediaria   TEXT,
    nome_regiao_intermediaria TEXT,
    id_regiao_imediata        TEXT,
    nome_regiao_imediata      TEXT,
    fonte                     TEXT NOT NULL,
    data_referencia           DATE,
    loaded_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT municipio_id_formato CHECK (id_municipio ~ '^[0-9]{7}$'),
    CONSTRAINT municipio_uf_formato CHECK (sigla_uf ~ '^[A-Z]{2}$')
);

CREATE INDEX IF NOT EXISTS idx_municipio_sigla_uf ON ref.municipio (sigla_uf);
CREATE INDEX IF NOT EXISTS idx_municipio_nome ON ref.municipio (nome);

CREATE TABLE IF NOT EXISTS ref.populacao_municipio (
    id_municipio    CHAR(7) NOT NULL REFERENCES ref.municipio (id_municipio),
    ano             INTEGER NOT NULL,
    populacao       INTEGER NOT NULL CHECK (populacao > 0),
    fonte           TEXT NOT NULL,
    data_referencia DATE,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_municipio, ano)
);

CREATE INDEX IF NOT EXISTS idx_populacao_ano ON ref.populacao_municipio (ano);
