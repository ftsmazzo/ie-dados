-- ie-dados: Base 3 extensão P0 — despesas pagas + doador originário

-- Pagamentos (liga a contratada via sq_despesa; sem município direto no CSV)
CREATE TABLE IF NOT EXISTS financeiro.despesa_paga_candidato (
    ano_eleicao              INTEGER NOT NULL,
    nr_turno                 INTEGER,
    cd_eleicao               INTEGER,
    sg_uf                    CHAR(2),
    cd_fonte_despesa         INTEGER,
    ds_fonte_despesa         TEXT,
    cd_origem_despesa        INTEGER,
    ds_origem_despesa        TEXT,
    cd_natureza_despesa      INTEGER,
    ds_natureza_despesa      TEXT,
    sq_despesa               BIGINT,
    sq_parcelamento_despesa  BIGINT,
    dt_pagto_despesa         DATE,
    ds_despesa               TEXT,
    vr_pagto_despesa         NUMERIC(18, 2),
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY LIST (ano_eleicao);

-- Doador originário (liga a receita via sq_receita)
CREATE TABLE IF NOT EXISTS financeiro.receita_doador_originario (
    ano_eleicao                   INTEGER NOT NULL,
    nr_turno                      INTEGER,
    cd_eleicao                    INTEGER,
    sg_uf                         CHAR(2),
    nr_cpf_cnpj_doador_originario TEXT,
    nm_doador_originario          TEXT,
    tp_doador_originario          TEXT,
    cd_cnae_doador_originario     INTEGER,
    ds_cnae_doador_originario     TEXT,
    sq_receita                    BIGINT,
    dt_receita                    DATE,
    ds_receita                    TEXT,
    vr_receita                    NUMERIC(18, 2),
    loaded_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY LIST (ano_eleicao);

DO $$
DECLARE
  y INT;
BEGIN
  FOREACH y IN ARRAY ARRAY[2018, 2020, 2022, 2024, 2026]
  LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS financeiro.despesa_paga_candidato_%s PARTITION OF financeiro.despesa_paga_candidato FOR VALUES IN (%s)',
      y, y
    );
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS financeiro.receita_doador_originario_%s PARTITION OF financeiro.receita_doador_originario FOR VALUES IN (%s)',
      y, y
    );
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_desp_paga_sq ON financeiro.despesa_paga_candidato (ano_eleicao, sq_despesa);
CREATE INDEX IF NOT EXISTS idx_desp_paga_origem ON financeiro.despesa_paga_candidato (ano_eleicao, ds_origem_despesa);
CREATE INDEX IF NOT EXISTS idx_doador_sq_rec ON financeiro.receita_doador_originario (ano_eleicao, sq_receita);
CREATE INDEX IF NOT EXISTS idx_doador_uf ON financeiro.receita_doador_originario (ano_eleicao, sg_uf);
