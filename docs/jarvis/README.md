# Jarvis do Prefeito — Ribeirão Preto (kit amanhã)

Objetivo: no PC do sócio, o **OpenJarvis** responde como assessor do Prefeito, usando o MCP **ie-dados** (eleitoral + Ribeirão). Sem SQL livre.

**Antes da demo:** ler `RECORTE-P0-PERGUNTAS.md` — só pergunte o que está ali.

## O que já está pronto

| Peça | Status |
|------|--------|
| MCP produção | `https://ie-dados-mcp.kxryyk.easypanel.host` |
| Auth com header | `Authorization: Bearer <MCP_TOKEN>` |
| Auth **sem header** (OpenJarvis) | URL `…/key/<MCP_TOKEN>/mcp` |
| Ribeirão Preto | `id_municipio=3543402` / `slug=ribeirao-preto` |
| Tools | `mun_*`, `election_*`, `finance_*`, `get_pib`/`get_idhm`, `plano_*`, … |

Token: EasyPanel (`ie-dados` → `mcp` → `MCP_TOKEN`) ou `.env.local`. **Não commitiar o token.**

---

## Ordem amanhã (Jarvis primeiro)

### 0) Antes de sair

- [ ] `https://ie-dados-mcp.kxryyk.easypanel.host/health` → `ok`
- [ ] Token anotado (cofre / papel)
- [ ] Pasta `docs/jarvis/` no pen drive / repo clonado

### 1) Instalar OpenJarvis (Windows)

```powershell
irm https://open-jarvis.github.io/OpenJarvis/install.ps1 | iex
jarvis doctor
```

(Alternativa: no Claude Code: “instale https://github.com/open-jarvis/OpenJarvis”.)

### 2) Plugar o MCP **sem header** (como o OpenJarvis pede)

No `config.toml` do Jarvis:

```toml
[tools.mcp]
enabled = true
servers = "mcp-servers.json"
```

Arquivo `mcp-servers.json` (copie de `openjarvis-mcp.example.json`):

```json
[
  {
    "name": "ie-dados",
    "url": "https://ie-dados-mcp.kxryyk.easypanel.host/key/COLE_O_MCP_TOKEN_AQUI/mcp"
  }
]
```

Só a URL — sem `headers`. O token vai no path `/key/<token>/`.

Se a versão do OpenJarvis tiver campo `token`, também vale:

```json
[{"name":"ie-dados","url":"https://ie-dados-mcp.kxryyk.easypanel.host/mcp","token":"COLE_O_MCP_TOKEN_AQUI"}]
```

### 3) Persona

Colar `persona-assessor-prefeito.md` nas instruções / memória do Jarvis (ou `CLAUDE.md` se estiver usando Claude Code no mesmo fluxo).

### 4) Smoke

Rodar `smoke-perguntas.md` (Saúde, IPTU, PIB, votos).

### 5) Claude Desktop / Cursor (mesmo MCP)

- **Claude Desktop (app):**  
  `C:\Users\anjo_\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json`  
  Padrão desta máquina: `npx mcp-remote` + URL `/key/<token>/mcp` (sem header).  
  Depois de editar: **fechar e reabrir o Claude**.
- Cursor: `%USERPROFILE%\.cursor\mcp.json`
- Claude Code CLI: `%USERPROFILE%\.claude.json` (é outro app — não é o Desktop)
- Templates: `openjarvis-mcp.example.json`, `mcp-ie-dados.example.json`, `claude-desktop-ie-dados.example.json`

---

## Arquivos do kit

| Arquivo | Uso |
|---------|-----|
| `README.md` | Este passo a passo |
| `openjarvis-mcp.example.json` | MCP sem header (path token) |
| `mcp-ie-dados.example.json` | Claude Code / Cursor |
| `persona-assessor-prefeito.md` | Prompt do assessor |
| `smoke-perguntas.md` | Aceite da demo |

## Regras na demo

1. Escopo Ribeirão (`3543402` / `ribeirao-preto`)
2. Não inventar número — só o que a tool devolver
3. Tom de assessor de gabinete
4. Se falhar: health → token na URL → `jarvis doctor`
