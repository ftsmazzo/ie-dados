#!/usr/bin/env python3
"""Scrape institucional do portal da Prefeitura de Ribeirão Preto → MD + manifest.

Gera docs/acervos/municipios/ribeirao-preto/ com secretarias, serviços e metadados.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "acervos" / "municipios" / "ribeirao-preto"
RAW_HTML = ROOT / "data" / "raw" / "acervos" / "ribeirao-preto" / "html"
MANIFEST = OUT / "_meta" / "manifest.json"

BASE = "https://www.ribeiraopreto.sp.gov.br"
UA = "ie-dados-acervo-municipios/0.1 (+ribeirao-preto; pesquisa institucional)"
SLEEP_S = 0.45
MAX_PAGES = 350
MAX_DEPTH = 3

ID_MUNICIPIO = "3543402"
SLUG_MUNICIPIO = "ribeirao-preto"

# Slugs de secretarias / órgãos (portal)
SEED_ORGAOS = {
    "administracao": "Secretaria Municipal da Administração",
    "assistencia-social": "Secretaria Municipal de Assistência Social",
    "fazenda": "Secretaria Municipal da Fazenda",
    "saude": "Secretaria Municipal da Saúde",
    "educacao": "Secretaria Municipal da Educação",
    "infraestrutura": "Secretaria Municipal de Infraestrutura e Zeladoria",
    "obras": "Secretaria Municipal de Obras",
    "planejamento": "Secretaria de Planejamento e Desenvolvimento Urbano e Habitação",
    "meio-ambiente": "Secretaria Municipal do Meio Ambiente, Agricultura e Sustentabilidade",
    "saerp": "SAERP - Secretaria de Água e Esgotos",
    "rpmobi": "RP Mobi",
    "cultura": "Secretaria Municipal da Cultura e Turismo",
    "esportes": "Secretaria Municipal de Esportes",
    "inovacao": "Secretaria Municipal de Inovação e Desenvolvimento",
    "tecnologia": "Secretaria de Tecnologia e Governo Digital",
    "justica": "Secretaria de Justiça",
    "comunicacao": "Secretaria de Comunicação",
    "governo": "Secretaria Municipal de Governo",
    "casa-civil": "Secretaria Municipal da Casa Civil",
    "cidadania": "Secretaria Municipal da Cidadania, Pessoa com Deficiência e Inclusão Social",
    "fundo-social": "Fundo Social de Solidariedade",
    "cohab": "COHAB",
    "coderp": "CODERP",
    "controladoria-geral-municipio": "Controladoria Geral do Município",
    "procon": "PROCON",
    "cidade-limpa": "Cidade Limpa",
    "coordenadoria-limpeza": "Coordenadoria de Limpeza",
    "canal-do-servidor": "Canal do Servidor",
    "poupatempo": "Poupatempo (municipal)",
}

SEED_URLS = [
    f"{BASE}/portal/principal/autoridades-do-executivo",
    f"{BASE}/portal/principal/telefones-uteis",
    f"{BASE}/portal/principal/administracao-municipal",
]
for slug in SEED_ORGAOS:
    SEED_URLS.extend(
        [
            f"{BASE}/portal/{slug}/",
            f"{BASE}/portal/{slug}/a-secretaria",
            f"{BASE}/portal/{slug}/secretario",
            f"{BASE}/portal/{slug}/carta-de-servicos",
            f"{BASE}/portal/{slug}/servicos-on-line",
        ]
    )

SKIP_PREFIXES = (
    "/portal/todas-noticias",
    "/portal/download/",
    "/portal/transparencia/portal-da-transparencia",  # enorme; só indexar landing se achar
)
SKIP_EXT = (".pdf", ".xls", ".xlsx", ".doc", ".docx", ".zip", ".jpg", ".png", ".gif", ".mp4")


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []
        self.title = ""
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._in_a = False
        self._a_href = ""
        self._a_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            self._in_a = True
            self._a_href = ad.get("href") or ""
            self._a_text = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._in_a:
            text = " ".join(self._a_text).strip()
            if self._a_href:
                self.links.append((text, self._a_href))
            self._in_a = False

    def handle_data(self, data):
        if self._skip:
            return
        t = data.strip()
        if not t:
            return
        if self._in_title:
            self.title += t + " "
        if self._in_a:
            self._a_text.append(t)
        self.parts.append(t)


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = resp.read()
        final = resp.geturl()
        return resp.status, data, final


def canonicalize(url: str) -> str | None:
    u = urllib.parse.urljoin(BASE, url)
    p = urllib.parse.urlparse(u)
    if p.scheme not in ("http", "https"):
        return None
    if "ribeiraopreto.sp.gov.br" not in p.netloc:
        return None
    path = p.path or "/"
    low = path.lower()
    if any(low.startswith(s) for s in SKIP_PREFIXES):
        return None
    if any(low.endswith(ext) for ext in SKIP_EXT):
        return None
    # normaliza
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urllib.parse.urlunparse(("https", "www.ribeiraopreto.sp.gov.br", path, "", "", ""))


def classify(url: str) -> tuple[str, str | None]:
    """Retorna (tipo, secretaria_slug)."""
    path = urllib.parse.urlparse(url).path.lower()
    m = re.match(r"^/portal/([^/]+)(?:/(.*))?$", path)
    if not m:
        return "outro", None
    slug, rest = m.group(1), (m.group(2) or "")
    if slug == "principal":
        if "autoridades" in rest or "telefone" in rest or "administracao-municipal" in rest:
            return "autoridade" if "autoridades" in rest else "contato", None
        return "institucional", None
    if slug in SEED_ORGAOS:
        if rest in ("", "a-secretaria", "secretario"):
            return "secretaria", slug
        if "servico" in rest or "carta" in rest or "atendimento" in rest or "posto" in rest:
            return "servico", slug
        return "institucional", slug
    return "outro", slug if slug not in ("download", "todas-noticias") else None


def clean_text(parts: list[str]) -> str:
    text = "\n".join(parts)
    # remove ruídos comuns de portal
    noise = [
        "Prefeitura Municipal de Ribeirão Preto",
        "Fale Conosco",
        "Centro Administrativo",
    ]
    lines = []
    seen = set()
    for line in text.splitlines():
        l = re.sub(r"\s+", " ", line).strip()
        if len(l) < 2:
            continue
        if l in noise and l in seen:
            continue
        seen.add(l)
        lines.append(l)
    # compacta
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def extract_phones(text: str) -> list[str]:
    pats = re.findall(r"\(?\d{2}\)?\s*\d{4,5}[-.\s]?\d{4}", text)
    uniq = []
    for p in pats:
        n = re.sub(r"\s+", " ", p).strip()
        if n not in uniq:
            uniq.append(n)
    return uniq[:20]


def slugify(name: str) -> str:
    s = name.lower()
    repl = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "pagina"


def write_md(path: Path, title: str, body: str, sources: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"_Município:_ Ribeirão Preto (SP) · `id_municipio={ID_MUNICIPIO}`",
        "",
        "## Conteúdo",
        "",
        body.strip() or "_(sem texto útil extraído)_",
        "",
        "## Fontes",
        "",
    ]
    for u in sources:
        lines.append(f"- {u}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "secretarias").mkdir(exist_ok=True)
    (OUT / "servicos").mkdir(exist_ok=True)
    (OUT / "_meta").mkdir(exist_ok=True)
    RAW_HTML.mkdir(parents=True, exist_ok=True)

    queue: list[tuple[str, int]] = []
    seen: set[str] = set()
    for u in SEED_URLS:
        cu = canonicalize(u)
        if cu and cu not in seen:
            seen.add(cu)
            queue.append((cu, 0))

    pages: list[dict] = []
    by_org: dict[str, list[dict]] = defaultdict(list)
    institucional: list[dict] = []

    while queue and len(pages) < MAX_PAGES:
        url, depth = queue.pop(0)
        try:
            status, data, final = fetch(url)
        except Exception as e:
            print(f"FAIL {url} {e}", flush=True)
            time.sleep(SLEEP_S)
            continue
        time.sleep(SLEEP_S)
        final_c = canonicalize(final) or url
        sha = hashlib.sha256(data).hexdigest()
        html_path = RAW_HTML / f"{sha[:16]}.html"
        if not html_path.exists():
            html_path.write_bytes(data)

        parser = _HTMLText()
        try:
            parser.feed(data.decode("utf-8", errors="replace"))
        except Exception:
            parser.feed(data.decode("latin-1", errors="replace"))
        text = clean_text(parser.parts)
        title = (parser.title or "").strip() or final_c
        tipo, org = classify(final_c)
        phones = extract_phones(text)
        rec = {
            "url": final_c,
            "title": title,
            "tipo": tipo,
            "secretaria_slug": org,
            "sha256": sha,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "text_len": len(text),
            "phones": phones,
            "html_file": str(html_path.relative_to(ROOT)).replace("\\", "/"),
            "text": text,
        }
        pages.append(rec)
        if org:
            by_org[org].append(rec)
        else:
            institucional.append(rec)
        print(f"OK d={depth} [{tipo}] {org or '-'} {final_c} ({len(text)}c)", flush=True)

        if depth >= MAX_DEPTH:
            continue
        for _t, href in parser.links:
            cu = canonicalize(href)
            if not cu or cu in seen:
                continue
            # prioriza mesmo órgão / seeds
            path = urllib.parse.urlparse(cu).path
            m = re.match(r"^/portal/([^/]+)", path)
            slug = m.group(1) if m else ""
            if slug in SEED_ORGAOS or slug == "principal" or depth == 0:
                seen.add(cu)
                queue.append((cu, depth + 1))

    # --- gerar MD por secretaria ---
    index_rows = []
    for slug, nome in sorted(SEED_ORGAOS.items(), key=lambda x: x[1]):
        items = by_org.get(slug, [])
        if not items:
            continue
        # página principal = a-secretaria ou maior texto
        items_sorted = sorted(
            items,
            key=lambda r: (
                0 if r["url"].endswith("/a-secretaria") else 1,
                -r["text_len"],
            ),
        )
        main = items_sorted[0]
        body_parts = [main["text"][:12000]]
        phones = []
        sources = []
        for r in items_sorted:
            sources.append(r["url"])
            for p in r["phones"]:
                if p not in phones:
                    phones.append(p)
        if phones:
            body_parts.insert(0, "### Contatos capturados\n\n" + "\n".join(f"- {p}" for p in phones))
        # serviços
        servs = [r for r in items if r["tipo"] == "servico"]
        if servs:
            body_parts.append("\n### Serviços / páginas relacionadas\n")
            for r in servs[:40]:
                body_parts.append(f"- **{r['title']}** — {r['url']}")
                # arquivo individual de serviço
                sp = OUT / "servicos" / f"{slug}-{slugify(r['title'])}.md"
                write_md(sp, r["title"], r["text"][:10000], [r["url"]])
        md_path = OUT / "secretarias" / f"{slug}.md"
        write_md(md_path, nome, "\n\n".join(body_parts), sources)
        index_rows.append((nome, slug, len(items), str(md_path.relative_to(OUT)).replace("\\", "/")))

    # autoridades / contatos
    aut = [p for p in institucional if p["tipo"] in ("autoridade", "contato", "institucional")]
    if aut:
        aut_sorted = sorted(aut, key=lambda r: -r["text_len"])
        body = "\n\n---\n\n".join(
            f"### {r['title']}\n\nFonte: {r['url']}\n\n{r['text'][:8000]}" for r in aut_sorted[:12]
        )
        write_md(
            OUT / "00-autoridades-e-contatos.md",
            "Autoridades e contatos — Ribeirão Preto",
            body,
            [r["url"] for r in aut_sorted[:12]],
        )

    # README índice
    readme = [
        "# Acervo Município — Ribeirão Preto (SP)",
        "",
        f"- `id_municipio`: `{ID_MUNICIPIO}`",
        f"- `slug`: `{SLUG_MUNICIPIO}`",
        f"- Fonte: {BASE}/portal/",
        f"- Páginas coletadas: **{len(pages)}**",
        f"- Secretarias/órgãos com MD: **{len(index_rows)}**",
        f"- Coleta: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Secretarias e órgãos",
        "",
        "| Órgão | Slug | Páginas | Arquivo |",
        "|-------|------|---------|---------|",
    ]
    for nome, slug, n, rel in index_rows:
        readme.append(f"| {nome} | `{slug}` | {n} | [{rel}]({rel}) |")
    readme += [
        "",
        "## Contatos gerais",
        "",
        "- [00-autoridades-e-contatos.md](00-autoridades-e-contatos.md)",
        "",
        "## Serviços",
        "",
        "Ver pasta `servicos/` (páginas classificadas como serviço).",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")

    # manifest (sem texto completo para ficar leve)
    manifest = {
        "id_municipio": ID_MUNICIPIO,
        "slug_municipio": SLUG_MUNICIPIO,
        "base": BASE,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "n_pages": len(pages),
        "n_secretarias": len(index_rows),
        "pages": [
            {k: v for k, v in p.items() if k != "text"}
            for p in pages
        ],
        "secretarias": [
            {"nome": n, "slug": s, "n_pages": c, "path": rel} for n, s, c, rel in index_rows
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE pages={len(pages)} secretarias={len(index_rows)} → {OUT}", flush=True)


if __name__ == "__main__":
    main()
