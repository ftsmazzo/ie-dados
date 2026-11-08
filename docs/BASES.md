# Catálogo de bases — ie-dados

Status possíveis: `aguardando ZIP` | `ZIP recebido` | `schema ok` | `carregada` | `validada` | `pronta`

Legado (`inteligencia-eleitoral*`, Postgres `iebrasil`, etc.): **fora de escopo**. Não migrar.

## Fila

| # | Domínio | Pasta raw | Fonte | Chave(s) | Status |
|---|---------|-----------|-------|----------|--------|
| 1 | Municípios + população | `data/raw/ibge/municipios/` e `data/raw/ibge/populacao/` | IBGE | `id_municipio` (7 dígitos) | aguardando ZIP |
| 2 | Urnas / resultados | `data/raw/tse/urna/` | TSE | `id_municipio` + `zona` (+ ano/turno/cargo) | aguardando ZIP |
| 3 | Financiamento / dinheiro | `data/raw/tse/prestacao/` | TSE | a definir com base 1–2 | aguardando ZIP |
| 4 | Senado / leis | `data/raw/congresso/` | fontes oficiais | a definir | aguardando ZIP |

## Base 1 — Municípios + população (próxima)

- **Objetivo:** diretório canônico de municípios brasileiros + série de população para cruzamentos futuros
- **Chave:** `id_municipio` = código IBGE de 7 dígitos
- **Pastas:**
  - `data/raw/ibge/municipios/` — malha/cadastro de municípios
  - `data/raw/ibge/populacao/` — estimativas e/ou Censo
- **Links oficiais:** ver seção “Próximo download” no README da sessão / mensagem do agente após Fase 0
- **Validação mínima (quando carregar):**
  - ~5.570 municípios ativos
  - `id_municipio` único, 7 dígitos
  - UF válida (27 UFs)
  - população > 0 onde houver ano de referência

## Notas

- ZIPs nunca entram no Git.
- Só avançamos para a base 2 quando a base 1 estiver `pronta`.
