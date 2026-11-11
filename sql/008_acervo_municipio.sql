-- ie-dados: Acervo Municípios (docs institucionais + chunks FTS)

CREATE SCHEMA IF NOT EXISTS docs;

CREATE TABLE IF NOT EXISTS docs.municipio_doc (
    id_doc            BIGSERIAL PRIMARY KEY,
    id_municipio      CHAR(7) NOT NULL REFERENCES ref.municipio (id_municipio),
    slug_municipio    TEXT NOT NULL,
    secretaria_slug   TEXT,
    tipo              TEXT NOT NULL CHECK (
        tipo IN ('secretaria', 'servico', 'contato', 'autoridade', 'institucional', 'outro')
    ),
    titulo            TEXT NOT NULL,
    path_md           TEXT NOT NULL,
    url_fonte         TEXT,
    sha256            TEXT,
    scraped_at        TIMESTAMPTZ,
    n_chunks          INTEGER NOT NULL DEFAULT 0,
    indexado_em       TIMESTAMPTZ,
    fonte             TEXT NOT NULL DEFAULT 'portal_prefeitura',
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT municipio_doc_path_unique UNIQUE (id_municipio, path_md)
);

CREATE INDEX IF NOT EXISTS idx_mun_doc_mun ON docs.municipio_doc (id_municipio);
CREATE INDEX IF NOT EXISTS idx_mun_doc_sec ON docs.municipio_doc (id_municipio, secretaria_slug);
CREATE INDEX IF NOT EXISTS idx_mun_doc_tipo ON docs.municipio_doc (id_municipio, tipo);

CREATE TABLE IF NOT EXISTS docs.municipio_chunk (
    id_chunk     BIGSERIAL PRIMARY KEY,
    id_doc       BIGINT NOT NULL REFERENCES docs.municipio_doc (id_doc) ON DELETE CASCADE,
    chunk_ord    INTEGER NOT NULL,
    secao        TEXT,
    texto        TEXT NOT NULL,
    tsv          TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(texto, ''))
    ) STORED,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT municipio_chunk_ord UNIQUE (id_doc, chunk_ord)
);

CREATE INDEX IF NOT EXISTS idx_mun_chunk_tsv ON docs.municipio_chunk USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_mun_chunk_doc ON docs.municipio_chunk (id_doc);
