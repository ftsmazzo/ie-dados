-- ie-dados: Base 3 — prestação de contas de candidatos (receitas + despesas contratadas)

CREATE SCHEMA IF NOT EXISTS financeiro;

-- Receitas de campanha (fato tipado; ligar a votos via sq_candidato + ano)
CREATE TABLE IF NOT EXISTS financeiro.receita_candidato (
    ano_eleicao          INTEGER NOT NULL,
    nr_turno             INTEGER,
    cd_eleicao           INTEGER,
    sg_uf                CHAR(2),
    sg_ue                TEXT,
    nm_ue                TEXT,
    cd_municipio_tse     INTEGER,
    id_municipio         CHAR(7),
    cd_cargo             INTEGER,
    ds_cargo             TEXT,
    sq_candidato         BIGINT,
    nr_candidato         INTEGER,
    nm_candidato         TEXT,
    nr_partido           INTEGER,
    sg_partido           TEXT,
    cd_fonte_receita     INTEGER,
    ds_fonte_receita     TEXT,
    cd_origem_receita    INTEGER,
    ds_origem_receita    TEXT,
    cd_natureza_receita  INTEGER,
    ds_natureza_receita  TEXT,
    nr_cpf_cnpj_doador   TEXT,
    nm_doador            TEXT,
    sq_receita           BIGINT,
    dt_receita           DATE,
    vr_receita           NUMERIC(18, 2),
    loaded_at            TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY LIST (ano_eleicao);

-- Despesas contratadas
CREATE TABLE IF NOT EXISTS financeiro.despesa_contratada_candidato (
    ano_eleicao            INTEGER NOT NULL,
    nr_turno               INTEGER,
    cd_eleicao             INTEGER,
    sg_uf                  CHAR(2),
    sg_ue                  TEXT,
    nm_ue                  TEXT,
    cd_municipio_tse       INTEGER,
    id_municipio           CHAR(7),
    cd_cargo               INTEGER,
    ds_cargo               TEXT,
    sq_candidato           BIGINT,
    nr_candidato           INTEGER,
    nm_candidato           TEXT,
    nr_partido             INTEGER,
    sg_partido             TEXT,
    cd_origem_despesa      INTEGER,
    ds_origem_despesa      TEXT,
    nm_fornecedor          TEXT,
    sq_despesa             BIGINT,
    dt_despesa             DATE,
    vr_despesa_contratada  NUMERIC(18, 2),
    loaded_at              TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY LIST (ano_eleicao);

DO $$
DECLARE
  y INT;
BEGIN
  FOREACH y IN ARRAY ARRAY[2018, 2020, 2022, 2024, 2026]
  LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS financeiro.receita_candidato_%s PARTITION OF financeiro.receita_candidato FOR VALUES IN (%s)',
      y, y
    );
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS financeiro.despesa_contratada_candidato_%s PARTITION OF financeiro.despesa_contratada_candidato FOR VALUES IN (%s)',
      y, y
    );
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_rec_cand ON financeiro.receita_candidato (ano_eleicao, sq_candidato);
CREATE INDEX IF NOT EXISTS idx_rec_mun ON financeiro.receita_candidato (id_municipio);
CREATE INDEX IF NOT EXISTS idx_rec_origem ON financeiro.receita_candidato (ano_eleicao, ds_origem_receita);
CREATE INDEX IF NOT EXISTS idx_desp_cand ON financeiro.despesa_contratada_candidato (ano_eleicao, sq_candidato);
CREATE INDEX IF NOT EXISTS idx_desp_mun ON financeiro.despesa_contratada_candidato (id_municipio);
CREATE INDEX IF NOT EXISTS idx_desp_origem ON financeiro.despesa_contratada_candidato (ano_eleicao, ds_origem_despesa);
