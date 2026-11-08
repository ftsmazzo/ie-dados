-- ie-dados: schema MCP (artefatos intermediários anti-token)

CREATE SCHEMA IF NOT EXISTS mcp;

CREATE TABLE IF NOT EXISTS mcp.artifact (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            TEXT NOT NULL,
    title           TEXT,
    columns         JSONB NOT NULL DEFAULT '[]'::jsonb,
    n_rows          INTEGER NOT NULL DEFAULT 0,
    sample_rows     JSONB NOT NULL DEFAULT '[]'::jsonb,
    rows_json       JSONB NOT NULL DEFAULT '[]'::jsonb,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_mcp_artifact_expires ON mcp.artifact (expires_at);
