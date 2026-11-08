-- ie-dados Base 4: PIB municipal (IBGE) + IDHM municipal (Atlas/PNUD)

CREATE SCHEMA IF NOT EXISTS ref;

CREATE TABLE IF NOT EXISTS ref.pib_municipio (
    id_municipio       CHAR(7) NOT NULL REFERENCES ref.municipio (id_municipio),
    ano                INTEGER NOT NULL CHECK (ano BETWEEN 1990 AND 2100),
    pib_mil            NUMERIC(18, 3),          -- R$ 1.000 a preços correntes
    pib_per_capita     NUMERIC(18, 2),          -- R$ 1,00
    vab_agro_mil       NUMERIC(18, 3),
    vab_industria_mil  NUMERIC(18, 3),
    vab_servicos_mil   NUMERIC(18, 3),          -- exceto adm pública
    vab_adm_mil        NUMERIC(18, 3),
    vab_total_mil      NUMERIC(18, 3),
    impostos_mil       NUMERIC(18, 3),
    fonte              TEXT NOT NULL,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_municipio, ano)
);

CREATE INDEX IF NOT EXISTS idx_pib_municipio_ano ON ref.pib_municipio (ano);

CREATE TABLE IF NOT EXISTS ref.idhm_municipio (
    id_municipio     CHAR(7) NOT NULL REFERENCES ref.municipio (id_municipio),
    ano              INTEGER NOT NULL CHECK (ano IN (1991, 2000, 2010)),
    idhm             NUMERIC(6, 3) NOT NULL,
    idhm_renda       NUMERIC(6, 3),
    idhm_longevidade NUMERIC(6, 3),
    idhm_educacao    NUMERIC(6, 3),
    fonte            TEXT NOT NULL,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_municipio, ano)
);

CREATE INDEX IF NOT EXISTS idx_idhm_municipio_ano ON ref.idhm_municipio (ano);
