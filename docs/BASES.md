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
- **Chave:** `id_municipio` = código IBGE de 7 dígitos (`COD. UF` + `COD. MUNIC`)
- **Pastas:**
  - `data/raw/ibge/municipios/` — Divisão Territorial Brasileira (DTB) / códigos
  - `data/raw/ibge/populacao/` — estimativas de população

### Downloads oficiais (você baixa e coloca nas pastas)

**A) Municípios (DTB 2025)**

1. Página: [Divisão Territorial Brasileira — downloads](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/23701-divisao-territorial-brasileira.html?=&t=downloads)
2. Baixar as tabelas DTB 2025 (ZIP com municípios / distritos / códigos)
3. Colocar o ZIP (e, se extrair, a planilha de municípios) em:
   `data/raw/ibge/municipios/`
4. Referência de códigos: [Códigos dos Municípios | IBGE](https://www.ibge.gov.br/explica/codigos-dos-municipios.php)

**B) População (estimativas 2024 — versão atualizada 30/12/2024)**

1. Índice FTP: [Estimativas_2024](https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2024/)
2. Preferir o arquivo mais recente:
   - [POP2024_20241230.xls](https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2024/POP2024_20241230.xls)
   - ou [POP2024_20241230.ods](https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2024/POP2024_20241230.ods)
3. Página de contexto: [Estimativas de população | IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html?edicao=41105)
4. Colocar o arquivo em:
   `data/raw/ibge/populacao/`

Quando os arquivos estiverem nas pastas, avise — montamos o DDL e a carga juntos.

### Validação mínima (quando carregar)

- ~5.570 municípios ativos
- `id_municipio` único, 7 dígitos
- UF válida (27 UFs)
- população > 0 onde houver ano de referência

## Notas

- ZIPs nunca entram no Git.
- Só avançamos para a base 2 quando a base 1 estiver `pronta`.
