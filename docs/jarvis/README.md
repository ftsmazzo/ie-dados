# Jarvis do Prefeito — Ribeirão Preto (kit amanhã)

Objetivo: no PC do sócio, um assistente que **municiária o Prefeito** com dados eleitorais + acervo institucional de Ribeirão Preto, via MCP tipado do **ie-dados** (sem SQL livre).

## O que já está pronto (nosso lado)

| Peça | Status |
|------|--------|
| MCP produção | `https://ie-dados-mcp.kxryyk.easypanel.host` |
| Auth | `Authorization: Bearer <MCP_TOKEN>` |
| Ribeirão Preto | `id_municipio=3543402` / `slug=ribeirao-preto` |
| Tools município | `mun_list`, `mun_list_secretarias`, `mun_get_secretaria`, `mun_retrieve`, `mun_search_servico` |
| Tools eleitorais / socio | `resolve_municipio`, `election_*`, `finance_*`, `get_pib`, `get_idhm`, `series_*`, `correlate`, `plano_*` |

Token: pegar no EasyPanel (`ie-dados` → `mcp` → env `MCP_TOKEN`) ou no `.env.local` da máquina que já usa o projeto. **Não colar o token neste repo.**

---

## Rota recomendada amanhã (mais estável)

O Reel do [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) é ótimo para voz/UI local. Para **consultar bem tools tipadas + Bearer**, a rota mais previsível no Windows é:

**Claude Code (ou Cursor) + MCP ie-dados + persona do assessor.**

OpenJarvis fica como **camada de voz/UI** (opcional, Passo B). Modelo local fraco costuma falhar em tool-use complexo; para municiar o Prefeito, use Claude (API/assinatura) como cérebro das tools.

### Checklist (imprimir / seguir em ordem)

#### 0) Antes de sair de casa

- [ ] Confirmar health: abrir `https://ie-dados-mcp.kxryyk.easypanel.host/health` → deve responder `ok`
- [ ] Anotar o `MCP_TOKEN` (papel/senha do cofre — não no WhatsApp)
- [ ] Levar este kit: pasta `docs/jarvis/` (ou o PDF/print do README)
- [ ] PC do sócio: Windows 10/11, internet, ~16 GB RAM ideal (8 GB mínimo apertado)

#### 1) Instalar Claude Code no PC do sócio

1. Instalar [Node.js LTS](https://nodejs.org/) (se ainda não tiver)
2. Abrir PowerShell e instalar Claude Code (comando oficial da Anthropic no momento da instalação)
3. Login na conta Anthropic do sócio / da empresa
4. Abrir uma pasta de trabalho, ex.: `C:\Jarvis-Prefeito`

#### 2) Conectar o MCP ie-dados

1. Copiar `mcp-ie-dados.example.json` → colar no `mcp.json` do Claude Code / Cursor do sócio  
   (Cursor: `%USERPROFILE%\.cursor\mcp.json` — mesclar com servers existentes)
2. Trocar `COLE_O_MCP_TOKEN_AQUI` pelo token real
3. Reiniciar o Claude Code / Cursor
4. Verificar se as tools `mun_*`, `election_*`, `list_domains` aparecem

Exemplo mínimo (HTTP + Bearer):

```json
{
  "mcpServers": {
    "ie-dados": {
      "type": "http",
      "url": "https://ie-dados-mcp.kxryyk.easypanel.host/mcp",
      "headers": {
        "Authorization": "Bearer COLE_O_MCP_TOKEN_AQUI"
      }
    }
  }
}
```

#### 3) Colar a persona

1. Abrir `persona-assessor-prefeito.md`
2. Colar como **instruções de projeto / system / CLAUDE.md** na pasta `C:\Jarvis-Prefeito`
3. Escopo fixo: Ribeirão Preto (`3543402`), sempre citar tool/fonte

#### 4) Smoke test (5 minutos)

Usar `smoke-perguntas.md`. Se as 5 perguntas baterem, está pronto para demo.

#### 5) (Opcional) OpenJarvis — voz / “Jarvis”

Só depois do MCP funcionar no Claude Code.

1. PowerShell (Admin se pedir):

```powershell
irm https://open-jarvis.github.io/OpenJarvis/install.ps1 | iex
```

2. `jarvis doctor` → tudo verde  
3. `jarvis` ou `jarvis gui`  
4. MCP externo: ver [docs OpenJarvis MCP](https://open-jarvis.github.io/OpenJarvis/user-guide/mcp-external-servers/)  
   - Hoje o schema documentado é `url` / `command` **sem headers Bearer**  
   - Se o ie-dados exigir Bearer e o OpenJarvis não aceitar header ainda: manter as perguntas de dados no Claude Code, e o OpenJarvis para voz/UI; ou usar um proxy local que injeta o header (avançado)

Fontes oficiais: [OpenJarvis GitHub](https://github.com/open-jarvis/OpenJarvis) · [site Stanford](https://openjarvis.stanford.edu/)

---

## Arquivos deste kit

| Arquivo | Uso |
|---------|-----|
| `README.md` | Este passo a passo |
| `mcp-ie-dados.example.json` | Template de conexão MCP |
| `persona-assessor-prefeito.md` | Prompt / CLAUDE.md |
| `smoke-perguntas.md` | Testes de aceite |

## Regras de ouro na demo

1. Sempre escopo Ribeirão (`3543402` / `ribeirao-preto`)
2. Não inventar telefone, endereço, voto ou PIB — só o que a tool devolver
3. Responder em português, tom de **assessor de gabinete**, não de chatbot genérico
4. Se a tool falhar: dizer “não encontrei na base” e sugerir a tool certa
