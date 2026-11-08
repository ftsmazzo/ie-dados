-- ie-dados: schema eleitoral (município + zona) + cruzamento TSE/IBGE

CREATE SCHEMA IF NOT EXISTS eleitoral;

-- Cruzamento oficial TSE ↔ IBGE
CREATE TABLE IF NOT EXISTS ref.municipio_tse (
    cd_municipio_tse  INTEGER PRIMARY KEY,
    id_municipio      CHAR(7), -- amarrado a ref.municipio na validação (sem FK rígida p/ tolerar defasagens)
    sg_uf             CHAR(2) NOT NULL,
    nm_municipio_tse  TEXT,
    nm_municipio_ibge TEXT,
    fonte             TEXT NOT NULL DEFAULT 'TSE municipio_tse_ibge',
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_municipio_tse_ibge ON ref.municipio_tse (id_municipio);

-- Detalhe da apuração por município/zona
CREATE TABLE IF NOT EXISTS eleitoral.detalhe_munzona (
    ano_eleicao            INTEGER NOT NULL,
    nr_turno               INTEGER NOT NULL,
    cd_eleicao             INTEGER,
    sg_uf                  CHAR(2) NOT NULL,
    cd_municipio_tse       INTEGER NOT NULL,
    id_municipio           CHAR(7),
    nr_zona                INTEGER NOT NULL,
    cd_cargo               INTEGER NOT NULL,
    ds_cargo               TEXT,
    qt_aptos               INTEGER,
    qt_comparecimento      INTEGER,
    qt_abstencoes          INTEGER,
    qt_total_votos_validos INTEGER,
    qt_votos_brancos       INTEGER,
    qt_votos_nulos         INTEGER,
    loaded_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_detalhe_ano ON eleitoral.detalhe_munzona (ano_eleicao);
CREATE INDEX IF NOT EXISTS idx_detalhe_mun ON eleitoral.detalhe_munzona (id_municipio);
CREATE INDEX IF NOT EXISTS idx_detalhe_zona ON eleitoral.detalhe_munzona (ano_eleicao, sg_uf, nr_zona);

-- Votação nominal por candidato/município/zona (colunas essenciais)
CREATE TABLE IF NOT EXISTS eleitoral.votacao_candidato_munzona (
    ano_eleicao                 INTEGER NOT NULL,
    nr_turno                    INTEGER NOT NULL,
    cd_eleicao                  INTEGER,
    sg_uf                       CHAR(2) NOT NULL,
    cd_municipio_tse            INTEGER NOT NULL,
    id_municipio                CHAR(7),
    nr_zona                     INTEGER NOT NULL,
    cd_cargo                    INTEGER NOT NULL,
    ds_cargo                    TEXT,
    sq_candidato                BIGINT,
    nr_candidato                INTEGER,
    nm_urna_candidato           TEXT,
    nr_partido                  INTEGER,
    sg_partido                  TEXT,
    qt_votos_nominais           INTEGER,
    qt_votos_nominais_validos   INTEGER,
    ds_sit_tot_turno            TEXT,
    loaded_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY LIST (ano_eleicao);

-- Partições 1998–2026 (gerais + municipais)
DO $$
DECLARE
  y INT;
BEGIN
  FOREACH y IN ARRAY ARRAY[1998,2000,2002,2004,2006,2008,2010,2012,2014,2016,2018,2020,2022,2024,2026]
  LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS eleitoral.votacao_candidato_munzona_%s PARTITION OF eleitoral.votacao_candidato_munzona FOR VALUES IN (%s)',
      y, y
    );
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_vot_mun ON eleitoral.votacao_candidato_munzona (id_municipio);
CREATE INDEX IF NOT EXISTS idx_vot_partido ON eleitoral.votacao_candidato_munzona (ano_eleicao, sg_partido);
CREATE INDEX IF NOT EXISTS idx_vot_cargo ON eleitoral.votacao_candidato_munzona (ano_eleicao, cd_cargo);
