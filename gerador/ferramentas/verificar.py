#!/usr/bin/env python3
"""Confere uma LP gerada antes de publicar: tira prints e procura problemas.

  python3 verificar.py <dist/slug> [--prints pasta] [--url https://... (confere a página no ar em vez da pasta)]

Gera prints em partes (desktop 1440 px e celular 390 px) para OLHAR com Read, e imprime um
relatório JSON. "erros" impede publicar; "avisos" pedem atenção. A conferência automática não
substitui olhar os prints: hierarquia, cortes, sobreposições e contraste se veem no olho.
"""
import argparse, asyncio, functools, http.server, json, re, socket, threading
from pathlib import Path

from PIL import Image

MARKETPLACES = ("amazon.com.br", "amazon.com", "a.co", "amzn.to", "mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com",
                "meli.la", "shopee.com.br", "shope.ee", "magazineluiza.com.br", "magalu.com", "americanas.com.br",
                "submarino.com.br", "shoptime.com.br", "estantevirtual.com.br")

JS = r"""
() => {
  document.querySelectorAll('.rev').forEach(e => e.classList.add('vis'));
  const r = {};
  r.overflow = document.documentElement.scrollWidth - window.innerWidth;
  r.imgs_quebradas = [...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.currentSrc || i.src);
  r.h1 = [...document.querySelectorAll('h1')].map(h => h.innerText.trim());
  r.titulo = document.title;
  r.descricao = (document.querySelector('meta[name=description]') || {}).content || '';
  r.og = (document.querySelector('meta[property="og:image"]') || {}).content || '';
  r.robots = (document.querySelector('meta[name=robots]') || {}).content || '';
  r.ctas = [...document.querySelectorAll('[data-cta]')].map(a => ({cta: a.dataset.cta, href: a.href, texto: a.innerText.trim()}));
  r.links = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
  r.texto = document.body.innerText;
  // elementos que saem da lateral da tela (causa comum de rolagem lateral no celular)
  r.vazando = [...document.querySelectorAll('body *')].filter(e => {
    const b = e.getBoundingClientRect(); const st = getComputedStyle(e);
    return b.width > 0 && b.right > window.innerWidth + 2 && st.position !== 'fixed' && !e.closest('[aria-hidden=true]') && st.overflow !== 'hidden';
  }).slice(0, 8).map(e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''));
  return r;
}
"""


CACHE_FONTES = Path.home() / ".cache" / "lp-fontes"


def _fontsource(familia):
    """Baixa a família do npm (@fontsource) uma vez e devolve a pasta com os .woff2 (latin)."""
    import subprocess, tarfile
    slug = re.sub(r"[^a-z0-9]+", "-", familia.lower()).strip("-")
    pasta = CACHE_FONTES / slug
    if pasta.exists():
        return slug, pasta
    try:
        meta = json.loads(subprocess.run(["curl", "-sS", f"https://registry.npmjs.org/@fontsource/{slug}/latest"],
                                         capture_output=True, text=True, timeout=30).stdout)
        tgz = CACHE_FONTES / f"{slug}.tgz"
        CACHE_FONTES.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sSL", "-o", str(tgz), meta["dist"]["tarball"]], check=True, timeout=60)
        pasta.mkdir()
        with tarfile.open(tgz) as t:
            for m in t.getmembers():
                if re.search(r"/files/.*-latin-\d+-(normal|italic)\.woff2$", m.name):
                    m.name = Path(m.name).name
                    t.extract(m, pasta, filter="data")
        tgz.unlink()
        return slug, pasta
    except Exception:
        return slug, None


def css_fontes_locais(url_css):
    """Troca o CSS do Google Fonts (bloqueado aqui) por @font-face com os mesmos arquivos vindos do npm."""
    from urllib.parse import parse_qs, urlparse, unquote
    regras = []
    for fam in parse_qs(urlparse(url_css).query).get("family", []):
        nome = unquote(fam.split(":")[0]).replace("+", " ")
        slug, pasta = _fontsource(nome)
        if not pasta:
            continue
        for arq in sorted(pasta.glob("*.woff2")):
            m = re.search(r"-latin-(\d+)-(normal|italic)\.woff2$", arq.name)
            regras.append(f"@font-face{{font-family:'{nome}';font-style:{m.group(2)};font-weight:{m.group(1)};"
                          f"font-display:block;src:url(/__fontes/{slug}/{arq.name}) format('woff2')}}")
    return "\n".join(regras)


def porta_livre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def marketplace(link):
    m = re.match(r"https://([^/?#]+)", (link or "").lower())
    return bool(m) and any(m.group(1) == d or m.group(1).endswith("." + d) for d in MARKETPLACES)


def fatiar(caminho, prefixo, altura):
    im = Image.open(caminho).convert("RGB")
    saidas = []
    for i, y in enumerate(range(0, im.height, altura), 1):
        p = caminho.parent / f"{prefixo}-{i}.jpg"
        im.crop((0, y, im.width, min(im.height, y + altura))).save(p, quality=80)
        saidas.append(str(p))
    caminho.unlink()
    return saidas


async def conferir(pasta, prints, url):
    from playwright.async_api import async_playwright
    srv = None
    if not url:
        class Q(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a): pass
        porta = porta_livre()
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(Q, directory=str(pasta)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{porta}/"
    prints.mkdir(parents=True, exist_ok=True)
    rel = {"erros": [], "avisos": [], "prints": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for nome, vp, dsf in (("desktop", {"width": 1440, "height": 900}, 1), ("celular", {"width": 390, "height": 844}, 2)):
            pg = await b.new_page(viewport=vp, device_scale_factor=dsf)
            console, falhas = [], []
            pg.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
            pg.on("requestfailed", lambda r: falhas.append(r.url))

            async def fontes_css(route):
                await route.fulfill(status=200, content_type="text/css", body=css_fontes_locais(route.request.url))

            async def fontes_arq(route):
                partes = route.request.url.split("/__fontes/")[1].split("/")
                arq = CACHE_FONTES / partes[0] / partes[1]
                await route.fulfill(status=200, content_type="font/woff2", body=arq.read_bytes()) if arq.exists() else await route.abort()
            await pg.route("https://fonts.googleapis.com/**", fontes_css)
            await pg.route("**/__fontes/**", fontes_arq)
            await pg.goto(url, wait_until="networkidle")
            await pg.wait_for_timeout(500)
            # rola até o fim para carregar as imagens lazy
            await pg.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }")
            await pg.wait_for_timeout(600)
            r = await pg.evaluate(JS)
            await pg.wait_for_timeout(800)
            tmp = prints / f"{nome}.png"
            await pg.screenshot(path=str(tmp), full_page=True)
            rel["prints"][nome] = fatiar(tmp, nome, 1800 if nome == "desktop" else 2600)
            locais = [f for f in falhas if "fonts.g" not in f]
            if locais: rel["erros"].append(f"{nome}: recursos que não carregaram: {locais[:6]}")
            if [f for f in falhas if "fonts.g" in f or "__fontes" in f] and "fontes" not in str(rel["avisos"]):
                rel["avisos"].append("alguma fonte não carregou nos prints (confira se o nome da família está certo)")
            if [c for c in console if "fonts.g" not in c and "ERR_" not in c]: rel["avisos"].append(f"{nome}: erros no console: {console[:4]}")
            if r["imgs_quebradas"]: rel["erros"].append(f"{nome}: imagens quebradas: {r['imgs_quebradas'][:6]}")
            if r["overflow"] > 1: rel["erros"].append(f"{nome}: rolagem lateral de {r['overflow']}px (vazando: {r['vazando']})")
            if nome == "desktop":
                info = r
            await pg.close()
        await b.close()
    if srv: srv.shutdown()

    t = info["texto"]
    if len(info["h1"]) != 1: rel["erros"].append(f"a página precisa de exatamente 1 h1 (tem {len(info['h1'])})")
    if not 20 <= len(info["titulo"]) <= 70: rel["avisos"].append(f"título com {len(info['titulo'])} caracteres (ideal 30–65)")
    if not 70 <= len(info["descricao"]) <= 160: rel["avisos"].append(f"descrição com {len(info['descricao'])} caracteres (ideal 120–160)")
    for lixo in ("**", "None", "undefined", "{{", "}}", "TODO", "Lorem"):
        if lixo in t: rel["erros"].append(f"texto da página contém '{lixo}'")
    if re.search(r"(?<![\w*])\*(?!\s)[^*\n]+\*(?![\w*])", t): rel["erros"].append("sobrou marcação de itálico (*texto*) no texto")
    compras = [c for c in info["ctas"] if c["cta"] != "instagram" and not c["cta"].startswith("loja")]
    if not compras: rel["erros"].append("nenhum botão de compra encontrado")
    for c in compras:
        if not marketplace(c["href"]): rel["erros"].append(f"botão de compra fora de marketplace: {c['href']}")
    for l in info["links"]:
        if l.startswith("http://"): rel["erros"].append(f"link sem https: {l}")
    rel["robots"] = info["robots"] or "index"
    rel["titulo"], rel["descricao"] = info["titulo"], info["descricao"]
    rel["ctas"] = info["ctas"]
    rel["ok"] = not rel["erros"]
    return rel


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta"); ap.add_argument("--prints"); ap.add_argument("--url")
    a = ap.parse_args()
    pasta = Path(a.pasta).resolve()
    rel = asyncio.run(conferir(pasta, Path(a.prints).resolve() if a.prints else pasta.parent / f"_prints-{pasta.name}", a.url))
    print(json.dumps(rel, ensure_ascii=False, indent=2))
