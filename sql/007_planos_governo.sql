-- ie-dados Base 5: catálogo de planos de governo + acervo textual (chunks)

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS docs;

CREATE TABLE IF NOT EXISTS ref.plano_governo (
    id_plano          BIGSERIAL PRIMARY KEY,
    ano_eleicao       INTEGER NOT NULL CHECK (ano_eleicao BETWEEN 1998 AND 2100),
    cd_cargo          INTEGER,                 -- 1 Pres, 3 Gov, 11 Pref (quando conhecido)
    ds_cargo          TEXT,
    sg_uf             CHAR(2),                 -- BR/null para Presidente
    id_municipio      CHAR(7) REFERENCES ref.municipio (id_municipio),
    sq_candidato      BIGINT NOT NULL,
    nm_candidato      TEXT,
    sg_partido        TEXT,
    eleito            BOOLEAN NOT NULL DEFAULT FALSE,
    ds_sit_tot_turno  TEXT,
    arquivo_nome      TEXT NOT NULL,
    arquivo_sha256    TEXT,
    url_origem        TEXT,
    path_raw          TEXT,
    n_chunks          INTEGER NOT NULL DEFAULT 0,
    indexado_em       TIMESTAMPTZ,
    fonte             TEXT NOT NULL DEFAULT 'TSE proposta_governo',
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT plano_governo_sq_ano_arquivo UNIQUE (ano_eleicao, sq_candidato, arquivo_nome)
);

CREATE INDEX IF NOT EXISTS idx_plano_ano_cargo ON ref.plano_governo (ano_eleicao, cd_cargo);
CREATE INDEX IF NOT EXISTS idx_plano_uf ON ref.plano_governo (sg_uf);
CREATE INDEX IF NOT EXISTS idx_plano_sq ON ref.plano_governo (sq_candidato, ano_eleicao);
CREATE INDEX IF NOT EXISTS idx_plano_eleito ON ref.plano_governo (eleito) WHERE eleito;
CREATE INDEX IF NOT EXISTS idx_plano_mun ON ref.plano_governo (id_municipio);

-- Acervo RAG (FTS no P0; embedding opcional depois)
CREATE TABLE IF NOT EXISTS docs.plano_chunk (
    id_chunk       BIGSERIAL PRIMARY KEY,
    id_plano       BIGINT NOT NULL REFERENCES ref.plano_governo (id_plano) ON DELETE CASCADE,
    chunk_ord      INTEGER NOT NULL,
    secao          TEXT,
    texto          TEXT NOT NULL,
    tsv            TSVECTOR GENERATED ALWAYS AS (to_tsvector('portuguese', coalesce(texto, ''))) STORED,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT plano_chunk_ord UNIQUE (id_plano, chunk_ord)
);

CREATE INDEX IF NOT EXISTS idx_plano_chunk_tsv ON docs.plano_chunk USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_plano_chunk_plano ON docs.plano_chunk (id_plano);
