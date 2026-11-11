# Recorte P0 — o que você PODE perguntar (sem passar vergonha)

Escopo demo: **Ribeirão Preto** (`3543402` / `ribeirao-preto`).  
Institucional = acervo curado. Números = tools eleitorais/socio já prontas.

Se a pergunta **não** estiver nesta lista → diga: *“ainda não está no recorte P0; ampliamos em breve”*.

---

## A) Institucional (tools `mun_*`)

### Sempre começar com escopo

`slug_municipio=ribeirao-preto` **ou** `id_municipio=3543402`

| # | Pergunta (fale assim) | Tool | Resposta concreta esperada |
|---|----------------------|------|----------------------------|
| 1 | Qual o telefone do gabinete do Prefeito? | `mun_retrieve` / autoridades | (16) 3977-9000 — Rua Américo Brasiliense, 426 |
| 2 | Qual o telefone da Secretaria da Saúde? | `mun_get_secretaria` `saude` ou telefones | (16) 3977-9300 |
| 3 | Quem é o secretário da Saúde e onde fica? | `mun_get_secretaria` `saude` | Dr. Maurício Godinho; Duque de Caxias, 675; 8h–17h |
| 4 | Ficha da Fazenda / quem atende IPTU presencial? | `mun_get_secretaria` `fazenda` (**não** `mun_search_servico`) | Raquel Scheffer; Poupatempo Kennedy 1500 com agendamento |
| 5 | Telefone e endereço da Educação | `mun_get_secretaria` `educacao` | (16) 3977-9100; Av. Treze de Maio, 157 |
| 6 | O que é a CABS e como agendar? | `mun_search_servico` “CABS” / “CadÚnico” | CadÚnico; Prudente de Morais 457; (16) 3605-2800 |
| 7 | Endereço e horário da Central de Benefícios Sociais | `mun_search_servico` “benefícios sociais” | mesma ficha CABS |
| 8 | Quais CRAS existem e telefone do CRAS Central? | `mun_search_servico` / `mun_retrieve` “CRAS” | lista + CRAS 1: São José 223; 98161-6736 / 3610-6495 |
| 9 | Contato da Assistência Social (SEMAS) | `mun_get_secretaria` `assistencia-social` | (16) 3611-6000; Prudente de Morais 457; e-mail gabinete |

### Frases que NÃO use no P0

- “Lista todas as UBS de Ribeirão”
- “Como emitir 2ª via de IPTU no site passo a passo”
- “Qual escola do meu bairro tem vaga?”
- Qualquer secretaria fora de: Assistência / Saúde / Fazenda / Educação (+ contatos gerais)

---

## B) Dados numéricos (já no MCP, seguros)

| # | Pergunta | Tools |
|---|----------|-------|
| 10 | PIB / PIB per capita de Ribeirão (ano recente) | `resolve_municipio` → `get_pib` |
| 11 | IDHM de Ribeirão | `get_idhm` |
| 12 | População | `get_populacao` |
| 13 | Resultado de prefeito 2024 em Ribeirão (votos) | `election_estimate` → `election_aggregate` (`ano_eleicao=2024`, `cd_cargo=11`) |
| 14 | Plano do presidente eleito 2026 sobre saúde | `plano_retrieve` (`eleito=true`, `cd_cargo=1`, `ano_eleicao=2026`) |

---

## C) Script de 3 minutos (demo)

1. “Telefone do Prefeito” → 3977-9000  
2. “O que é a CABS e como agendo?” → CadÚnico + Prudente de Morais 457 + 3605-2800  
3. “Onde atendo IPTU presencial?” → Poupatempo Kennedy 1500  
4. “PIB per capita de Ribeirão” → `get_pib`  
5. “Se precisar de CRAS da região Central?” → CRAS 1 na lista  

Promessa honesta: *“Este é o recorte P0 curado; o scrape amplo vem na próxima entrega.”*
