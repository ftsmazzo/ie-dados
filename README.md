# ie-dados

Base de dados definitiva da Inteligência Eleitoral / Fábrica IA.

Plataforma construída com rigor, base a base, para alimentar agentes (Claude, GPT, Manus) via MCP e, no futuro, modelos preditivos. Não reaproveita o legado criado às pressas.

## Princípios

- Uma chave territorial comum: código IBGE do município (7 dígitos)
- Dados oficiais em ZIP na pasta local; o Git guarda schema e documentação, não os arquivos brutos
- Cada base só é marcada como pronta após carga + validação (contagens, nulos, FK, amostra)
- Sem atropelo: municípios/população → urnas (município/zona) → dinheiro/Senado/leis → demais

## Estrutura

```
docs/           Catálogo de bases e schemas
data/raw/       ZIPs oficiais (gitignore)
data/processed/ Derivados intermediários (gitignore)
sql/            Migrations / DDL versionado
mcp/            Servidor MCP (fase posterior)
```

## Ordem das bases

1. Diretório de municípios + população
2. Resultados de urna (município + zona eleitoral)
3. Bases relacionadas (financiamento, Senado, leis)
4. Demais bases e preditividade

Ver [docs/BASES.md](docs/BASES.md).

## Produção

- EasyPanel: projeto `ie-dados` na Fábrica-IA
- Postgres: serviço `postgres`, database `iedados`
- Base 1: `ref.municipio` + `ref.populacao_municipio` (5.571 municípios)
- Base 2: `eleitoral.*` (~45 mi votos mun/zona, 1998–2026)
- MCP: ainda não implantado

### Recarregar bases (local)

```bash
python scripts/prepare_ref_ibge.py
python scripts/load_ref_ibge.py
# DATABASE_URL apontando para o Postgres do projeto
python scripts/load_eleitoral.py
```

## Colaboração com dados

1. Combinamos pasta + link oficial da base
2. O ZIP vai em `data/raw/...`
3. Schema em `sql/` + carga + validação
4. Status atualizado em `docs/BASES.md`
