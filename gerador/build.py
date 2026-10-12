#!/usr/bin/env python3
"""Gera uma LP de livro único a partir de um lp.json.

Uso:
  python3 build.py caminho/para/lp.json [--previa] [--saida pasta]

A pasta do lp.json precisa ter as imagens citadas nele (hero, diferenciais,
bio, final, instagram). O resultado vai para <saida>/<slug>/ pronto para subir.
--previa marca a página como noindex (para o subdomínio de teste).
"""
import argparse, datetime, html, json, re, shutil, sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from PIL import Image, ImageOps

AQUI = Path(__file__).resolve().parent

FONTES = {
    "DM Serif Display":    {"google": "DM+Serif+Display",              "peso": 400, "fallback": "Georgia, serif"},
    "Playfair Display":    {"google": "Playfair+Display:wght@700",     "peso": 700, "fallback": "Georgia, serif"},
    "Fraunces":            {"google": "Fraunces:opsz,wght@9..144,600", "peso": 600, "fallback": "Georgia, serif"},
    "Bricolage Grotesque": {"google": "Bricolage+Grotesque:wght@700",  "peso": 700, "fallback": "system-ui, sans-serif"},
    "Baloo 2":             {"google": "Baloo+2:wght@700",              "peso": 700, "fallback": "system-ui, sans-serif"},
    "Cormorant Garamond":  {"google": "Cormorant+Garamond:wght@600",   "peso": 600, "fallback": "Georgia, serif"},
    "Instrument Serif":    {"google": "Instrument+Serif",              "peso": 400, "fallback": "Georgia, serif"},
    "Space Grotesk":       {"google": "Space+Grotesk:wght@700",        "peso": 700, "fallback": "system-ui, sans-serif"},
}
CLARO_FIXO, ESCURO_FIXO = "#FFF8F0", "#2A1F18"
LARGURAS = (800, 1400)


# ---------- texto ----------
def rich(s):
    """Escapa HTML e aceita **negrito** e *itálico* no texto vindo do card."""
    if s is None:
        return None
    s = html.escape(str(s).strip(), quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    return Markup(s)


def plain(s):
    return re.sub(r"\*+", "", str(s or "")).strip()


# ---------- cor ----------
def _lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def escurecer(h, f):
    h = h.lstrip("#")
    return "#" + "".join(f"{max(0, int(int(h[i:i + 2], 16) * (1 - f))):02X}" for i in (0, 2, 4))


def preparar_cores(c, avisos):
    c = dict(c)
    c.setdefault("botao", c["destaque"])
    c.setdefault("botao_texto", CLARO_FIXO)
    # Rodapé: escolhe o texto de melhor contraste e, se ainda faltar, escurece o fundo.
    for _ in range(12):
        txt = CLARO_FIXO if contraste(CLARO_FIXO, c["rodape"]) >= contraste(ESCURO_FIXO, c["rodape"]) else ESCURO_FIXO
        if contraste(txt, c["rodape"]) >= 4.5:
            break
        c["rodape"] = escurecer(c["rodape"], 0.06) if txt == CLARO_FIXO else c["rodape"]
    c["rodape_texto"] = txt
    c["rodape_texto_claro"] = txt == CLARO_FIXO
    checagens = [
        ("texto", "claro", 4.5), ("texto", "medio", 4.5), ("texto_claro", "escuro", 4.5),
        ("botao_texto", "botao", 4.5), ("destaque", "medio", 4.5), ("destaque", "claro", 4.5),
    ]
    for a, b, m in checagens:
        r = contraste(c[a], c[b])
        if r < m:
            avisos.append(f"contraste baixo: {a} sobre {b} = {r:.2f} (mínimo {m})")
    return c


# ---------- imagens ----------
def processar_imagem(origem, nome, destino, alt="", larguras=LARGURAS):
    im = ImageOps.exif_transpose(Image.open(origem))
    alfa = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA" if alfa else "RGB")
    w, h = im.size
    for lw in larguras:
        alvo = im if w <= lw else im.resize((lw, round(h * lw / w)), Image.LANCZOS)
        alvo.save(destino / f"{nome}-{lw}.webp", "WEBP", quality=84, method=6)
        if lw == larguras[-1]:
            if alfa:
                alvo.save(destino / f"{nome}-{lw}.png", "PNG", optimize=True)
            else:
                alvo.save(destino / f"{nome}-{lw}.jpg", "JPEG", quality=84, optimize=True, progressive=True)
    fw = min(w, larguras[-1])
    return {"arquivo": nome, "w": fw, "h": round(h * fw / w), "alt": alt,
            "ext": "png" if alfa else "jpg", "max": larguras[-1], "min": larguras[0]}


def og_imagem(origem, destino):
    im = ImageOps.exif_transpose(Image.open(origem)).convert("RGB")
    ImageOps.fit(im, (1200, 630), Image.LANCZOS, centering=(0.5, 0.45)).save(
        destino / "og.jpg", "JPEG", quality=85, optimize=True, progressive=True)
    return "og.jpg"


def favicon(cor, destino):
    (destino / "favicon.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{cor}"/>'
        '<path d="M14 20c7-3 13-2 18 2v24c-5-4-11-5-18-2zM50 20c-7-3-13-2-18 2v24c5-4 11-5 18-2z" fill="none" '
        'stroke="#FFF8F0" stroke-width="3.2" stroke-linejoin="round"/></svg>', encoding="utf-8")


# ---------- compra ----------
MARKETPLACES = ("amazon.com.br", "amazon.com", "a.co", "amzn.to", "mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com",
                "meli.la", "shopee.com.br", "shope.ee", "magazineluiza.com.br", "magalu.com", "americanas.com.br",
                "submarino.com.br", "shoptime.com.br", "estantevirtual.com.br", "umlivro.com.br")


def checar_compra(compra):
    """Só links oficiais de marketplace: nada de site/catálogo da editora, site do autor, WhatsApp etc."""
    for l in [compra["principal"]] + compra.get("outros", []):
        m = re.match(r"https://([^/?#]+)", (l.get("url") or "").lower())
        host = m.group(1) if m else ""
        if not any(host == d or host.endswith("." + d) for d in MARKETPLACES):
            raise SystemExit(f"Link de compra fora de marketplace: {l.get('url')} (só Amazon, Mercado Livre, Shopee, Magalu…)")


# ---------- montagem ----------
def obrigatorio(d, caminho):
    atual = d
    for p in caminho.split("."):
        if not isinstance(atual, dict) or not atual.get(p):
            raise SystemExit(f"Campo obrigatório ausente no lp.json: {caminho}")
        atual = atual[p]


def montar(arq, previa=False, saida=None, url_base=None):
    arq = Path(arq).resolve()
    base = arq.parent
    d = json.loads(arq.read_text(encoding="utf-8"))
    checar_compra(d.get("compra") or {"principal": {}})
    modelo = d.get("modelo", "livro-unico")
    if modelo not in MODELOS:
        raise SystemExit(f"modelo '{modelo}' ainda não existe. Disponíveis: {', '.join(MODELOS)}")
    if modelo == "livro-grafico":
        return montar_grafico(d, base, previa, saida, url_base)
    if modelo == "infantil":
        return montar_infantil(d, base, previa, saida, url_base)
    for c in ["slug", "subdominio", "livro.titulo", "livro.autor", "compra.principal.url",
              "hero.tagline", "hero.descricao", "hero.imagem", "sinopse.titulo", "sinopse.paragrafos",
              "diferenciais.titulo", "diferenciais.itens", "bio.nome", "bio.paragrafos",
              "final.titulo", "final.texto", "final.imagem", "tema.cores"]:
        obrigatorio(d, c)
    if not 2 <= len(d["diferenciais"]["itens"]) <= 4:
        raise SystemExit("diferenciais.itens precisa ter de 2 a 4 itens")

    avisos = []
    out = Path(saida or AQUI / "dist").resolve() / d["slug"]
    if out.exists():
        shutil.rmtree(out)
    (out / "img").mkdir(parents=True)
    img_dir = out / "img"

    livro = d["livro"]
    titulo = plain(livro["titulo"])
    fonte_nome = d["tema"].get("fonte_titulo", "DM Serif Display")
    if fonte_nome not in FONTES:
        raise SystemExit(f"fonte_titulo inválida: {fonte_nome}. Use uma de: {', '.join(FONTES)}")
    f = FONTES[fonte_nome]
    cores = preparar_cores(d["tema"]["cores"], avisos)

    def img(chave, alt):
        return processar_imagem(base / chave, Path(chave).stem.replace(" ", "-"), img_dir, alt)

    hero_img = img(d["hero"]["imagem"], d["hero"].get("alt") or f"Livro {titulo}, de {livro['autor']}")
    dif_img = img(d["diferenciais"]["imagem"], d["diferenciais"].get("alt", "")) if d["diferenciais"].get("imagem") else None
    if dif_img and d["diferenciais"].get("proporcao") == "natural":
        dif_img["prop"] = f'{dif_img["w"]} / {dif_img["h"]}'
    divisor = None
    if d["tema"].get("divisor"):
        dv = Image.open(base / d["tema"]["divisor"]).convert("RGBA")
        dv.thumbnail((640, 640), Image.LANCZOS)
        divisor = {"w": dv.width, "h": dv.height}
        for chave, cor in (("escuro", cores["destaque"]), ("claro", cores["texto_claro"])):
            rgb = tuple(int(cor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            tinta = Image.new("RGBA", dv.size, rgb + (255,))
            tinta.putalpha(dv.getchannel("A"))
            tinta.save(img_dir / f"divisor-{chave}.webp", "WEBP", quality=90)
            divisor[chave] = f"divisor-{chave}.webp"
    # Textura: padrão repetível tirado do miolo (máscara em tons de cinza: branco = traço), tingido
    # numa cor da paleta e aplicado de leve no fundo do hero e do trecho.
    textura = None
    if d["tema"].get("textura"):
        tx = Image.open(base / d["tema"]["textura"])
        mascara = tx.getchannel("A") if tx.mode in ("RGBA", "LA") else tx.convert("L")
        cor_tx = cores.get(d["tema"].get("textura_cor", "escuro"), d["tema"].get("textura_cor"))
        rgb = tuple(int(cor_tx.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        op = float(d["tema"].get("textura_opacidade", .08))
        tinta = Image.new("RGBA", mascara.size, rgb + (255,))
        tinta.putalpha(mascara.point(lambda v: round(v * op)))
        tinta.save(img_dir / "textura.webp", "WEBP", quality=90)
        textura = {"arquivo": "textura.webp", "largura": int(d["tema"].get("textura_largura", 260))}
    galeria = None
    if d.get("galeria", {}).get("itens"):
        g = d["galeria"]
        if not 2 <= len(g["itens"]) <= 4:
            raise SystemExit("galeria.itens precisa ter de 2 a 4 ilustrações")
        galeria = {"titulo": rich(g.get("titulo", "Das páginas do livro")), "intro": rich(g.get("intro")),
                   "itens": [{"imagem": img(i["imagem"], i.get("alt") or plain(i.get("legenda", ""))),
                              "legenda": rich(i.get("legenda"))} for i in g["itens"]]}
    fin_img = img(d["final"]["imagem"], d["final"].get("alt") or f"Livro {titulo}")
    bio_img = img(d["bio"]["foto"], livro["autor"]) if d["bio"].get("foto") else None
    shutil.copy(AQUI / "assets" / "logo-global.png", img_dir / "logo-global.png")

    instagram = None
    if d.get("instagram", {}).get("usuario"):
        ig = d["instagram"]
        usuario = ig["usuario"].lstrip("@")
        foto = None  # foto do perfil do Instagram não é usada (decisão de 10/2026): só a tag
        instagram = {"usuario": usuario, "url": ig.get("url") or f"https://www.instagram.com/{usuario}/",
                     "foto": foto, "rotulo": ig.get("rotulo", "Siga o autor")}

    ornamento = None
    if d["tema"].get("ornamento"):
        orn = Image.open(base / d["tema"]["ornamento"]).convert("RGBA")
        orn.thumbnail((760, 760), Image.LANCZOS)
        orn.save(img_dir / "ornamento.webp", "WEBP", quality=86)
        ornamento = "ornamento.webp"
    og = (og_grafico(cores["medio"], base / d["hero"]["imagem"], img_dir) if hero_img["ext"] == "png"
          else og_imagem(base / d["hero"]["imagem"], img_dir))
    favicon(cores["destaque"], out)

    url = url_base or f"https://{d['subdominio']}.bibliomarket.com.br/"

    jsonld = {"@context": "https://schema.org", "@type": "Book", "name": titulo,
              "author": {"@type": "Person", "name": livro["autor"]}, "inLanguage": "pt-BR",
              "url": url, "image": f"{url}img/{og}", "description": plain(d["hero"]["descricao"])}
    if livro.get("isbn"): jsonld["isbn"] = livro["isbn"]
    jsonld["offers"] = {"@type": "Offer", "url": d["compra"]["principal"]["url"], "availability": "https://schema.org/InStock"}

    seo = d.get("seo", {})
    seo_titulo = seo.get("titulo") or f"{titulo} · {livro['autor']}"
    seo_desc = seo.get("descricao") or plain(d["hero"]["descricao"])
    if len(seo_desc) > 160:
        avisos.append(f"seo.descricao com {len(seo_desc)} caracteres (ideal até 160)")

    ctx = {
        "previa": previa, "url": url, "ano": d.get("ano") or datetime.date.today().year,
        "seo": {"titulo": seo_titulo, "descricao": seo_desc}, "og_imagem": og,
        "fonte": {"google": f["google"], "peso": f["peso"], "css": Markup(f'"{fonte_nome}", {f["fallback"]}')},
        "cores": cores, "livro": {**livro, "titulo": titulo},
        "ornamento": ornamento, "ornamento_opacidade": d["tema"].get("ornamento_opacidade", .9), "divisor": divisor,
        "textura": textura, "galeria": galeria,
        "jsonld": Markup(json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")),
        "instagram": instagram,
        "compra": {"principal": d["compra"]["principal"], "outros": d["compra"].get("outros", []),
                   "texto_botao": d["compra"].get("texto_botao", "Adquira o seu exemplar"),
                   "texto_topo": d["compra"].get("texto_topo", "Comprar")},
        "hero": {"tagline": rich(d["hero"]["tagline"]), "descricao": rich(d["hero"]["descricao"]), "imagem": hero_img},
        "sinopse": {"titulo": rich(d["sinopse"]["titulo"]), "paragrafos": [rich(p) for p in d["sinopse"]["paragrafos"]]},
        "diferenciais": {"titulo": rich(d["diferenciais"]["titulo"]), "imagem": dif_img,
                         "itens": [{"titulo": rich(i["titulo"]), "texto": rich(i["texto"])} for i in d["diferenciais"]["itens"]]},
        "trecho": ({"texto": rich(d["trecho"]["texto"]), "referencia": d["trecho"].get("referencia") or titulo}
                   if d.get("trecho", {}).get("texto") else None),
        "depoimentos": ({"titulo": rich(d["depoimentos"].get("titulo", "O que os leitores dizem")),
                         "itens": [{"texto": rich(x["texto"]), "nome": x["nome"], "papel": x.get("papel")} for x in d["depoimentos"]["itens"]]}
                        if d.get("depoimentos", {}).get("itens") else None),
        "bio": {"rotulo": d["bio"].get("rotulo", "Sobre o autor"), "nome": d["bio"]["nome"], "foto": bio_img,
                "paragrafos": [rich(p) for p in d["bio"]["paragrafos"]]},
        "final": {"titulo": rich(d["final"]["titulo"]), "texto": rich(d["final"]["texto"]),
                  "fecho": rich(d["final"].get("fecho")), "imagem": fin_img},
    }
    env = Environment(loader=FileSystemLoader(AQUI / "template"), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    (out / "index.html").write_text(env.get_template("livro-unico.html.j2").render(**ctx), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if previa else f"User-agent: *\nAllow: /\n", encoding="utf-8")

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"OK  {out}  ({total / 1024:.0f} KB)")
    for a in avisos:
        print("AVISO", a)
    return out


# ================== modelo "livro-grafico" ==================
import random

FONTES_EXTRA = {
    "Anton": {"google": "family=Anton", "css": '"Anton", Impact, "Arial Narrow", sans-serif'},
    "Montserrat": {"google": "family=Montserrat:ital,wght@0,400;0,600;0,700;0,800;1,400;1,600", "css": '"Montserrat", system-ui, Arial, sans-serif'},
    "Bricolage Grotesque": {"google": "family=Bricolage+Grotesque:wght@400;600;700;800", "css": '"Bricolage Grotesque", system-ui, sans-serif'},
    "DM Sans": {"google": "family=DM+Sans:ital,wght@0,400;0,700;0,800;1,400", "css": '"DM Sans", system-ui, sans-serif'},
    "DM Serif Display": {"google": "family=DM+Serif+Display", "css": '"DM Serif Display", Georgia, serif'},
    "Baloo 2": {"google": "family=Baloo+2:wght@600;700;800", "css": '"Baloo 2", system-ui, sans-serif'},
    "Fraunces": {"google": "family=Fraunces:opsz,wght@9..144,600", "css": '"Fraunces", Georgia, serif'},
}


def _rachadura(rnd, x, y, ang, comp, passos, galhos, paths, prof=0):
    """Linha quebrada que lembra as fissuras de lava da capa, com ramificações."""
    import math
    pts = [(x, y)]
    seg = comp / passos
    for _ in range(passos):
        ang += rnd.uniform(-0.55, 0.55)
        x += math.cos(ang) * seg * rnd.uniform(.7, 1.3)
        y += math.sin(ang) * seg * rnd.uniform(.7, 1.3)
        pts.append((x, y))
        if prof < 2 and rnd.random() < galhos:
            _rachadura(rnd, x, y, ang + rnd.choice([-1, 1]) * rnd.uniform(.6, 1.2), comp * .45, max(3, passos // 2), galhos * .5, paths, prof + 1)
    paths.append("M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts))


def svg_rachaduras(semente, w, h, modo, classe="rachaduras", estilo=""):
    import math
    rnd = random.Random(semente)
    paths = []
    if modo == "radial":
        cx, cy = w / 2, h * .55
        for i in range(7):
            a = -math.pi / 2 + (i - 3) * .55 + rnd.uniform(-.15, .15) + (math.pi if i % 2 and rnd.random() < .5 else 0)
            r0 = w * .30
            _rachadura(rnd, cx + math.cos(a) * r0, cy + math.sin(a) * r0 * .9, a, w * .32, 9, .35, paths)
    else:  # borda horizontal
        x = -10
        while x < w:
            comp = rnd.uniform(w * .18, w * .32)
            _rachadura(rnd, x, rnd.uniform(h * .15, h * .5), rnd.uniform(-.25, .25), comp, 10, .3, paths)
            x += comp * rnd.uniform(.7, 1.0)
    d = "".join(f'<path d="{p}"/>' for p in paths)
    return Markup(f'<svg class="{classe}" style="{estilo}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
                  f'<g class="brilho" filter="url(#lv{semente})">{d}</g><g>{d}</g>'
                  f'<defs><filter id="lv{semente}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5"/></filter></defs></svg>')


def og_grafico(fundo, livro_png, destino):
    bg = Image.new("RGB", (1200, 630), fundo)
    bk = Image.open(livro_png).convert("RGBA")
    bk.thumbnail((520, 560), Image.LANCZOS)
    bg.paste(bk, ((1200 - bk.width) // 2, (630 - bk.height) // 2), bk)
    bg.save(destino / "og.jpg", "JPEG", quality=86, optimize=True, progressive=True)
    return "og.jpg"


def retrato(origem, destino, nome):
    im = ImageOps.fit(ImageOps.exif_transpose(Image.open(origem)).convert("RGB"), (236, 236), Image.LANCZOS)
    im.save(destino / f"{nome}.webp", "WEBP", quality=86)
    return f"{nome}.webp"


def montar_grafico(d, base, previa, saida, url_base):
    for c in ["slug", "subdominio", "livro.titulo", "livro.autor", "compra.principal.url", "hero.imagem", "hero.tagline",
              "sinopse.titulo", "sinopse.paragrafos", "diferenciais.titulo", "diferenciais.itens", "bio.nome",
              "bio.paragrafos", "final.titulo", "final.texto", "final.imagem", "tema.cores"]:
        obrigatorio(d, c)
    avisos = []
    out = Path(saida or AQUI / "dist").resolve() / d["slug"]
    if out.exists():
        shutil.rmtree(out)
    img_dir = out / "img"
    img_dir.mkdir(parents=True)
    livro = d["livro"]
    titulo = plain(livro["titulo"])
    c = d["tema"]["cores"]
    ft, fx = d["tema"].get("fonte_titulo", "Anton"), d["tema"].get("fonte_texto", "Montserrat")
    for f in (ft, fx):
        if f not in FONTES_EXTRA:
            raise SystemExit(f"fonte inválida: {f}. Use uma de: {', '.join(FONTES_EXTRA)}")
    motivos = d["tema"].get("motivos", [])

    hero_img = processar_imagem(base / d["hero"]["imagem"], "livro", img_dir, d["hero"].get("alt") or f"Livro {titulo}", (520, 900))
    fin_img = processar_imagem(base / d["final"]["imagem"], "final", img_dir, d["final"].get("alt", ""), (420, 760))
    bio_img = processar_imagem(base / d["bio"]["foto"], "autor", img_dir, livro["autor"], (300, 600)) if d["bio"].get("foto") else None
    shutil.copy(AQUI / "assets" / "logo-global.png", img_dir / "logo-global.png")
    pers = None
    if d.get("personagens", {}).get("itens"):
        pp = d["personagens"]
        pers = {"titulo": rich(pp["titulo"]), "intro": rich(pp.get("intro")),
                "itens": [{"nome": i["nome"], "forca": i["forca"], "cor": i.get("cor", c["lava"]), "texto": rich(i["texto"]),
                           "foto": retrato(base / i["imagem"], img_dir, "p-" + re.sub(r"\W+", "-", i["nome"].lower()))} for i in pp["itens"]]}

    instagram = None
    if d.get("instagram", {}).get("usuario"):
        u = d["instagram"]["usuario"].lstrip("@")
        instagram = {"usuario": u, "url": d["instagram"].get("url") or f"https://www.instagram.com/{u}/"}

    og = og_grafico(c["noite"], base / d["hero"]["imagem"], img_dir)
    favicon(c["vermelho"], out)
    url = url_base or f"https://{d['subdominio']}.bibliomarket.com.br/"

    jsonld = {"@context": "https://schema.org", "@type": "Book", "name": plain(livro.get("titulo_completo") or titulo),
              "author": {"@type": "Person", "name": livro["autor"]}, "inLanguage": "pt-BR", "url": url,
              "image": f"{url}img/{og}", "description": plain(d["hero"].get("descricao") or d["hero"]["tagline"])}
    if livro.get("isbn"): jsonld["isbn"] = livro["isbn"]
    jsonld["offers"] = {"@type": "Offer", "url": d["compra"]["principal"]["url"], "availability": "https://schema.org/InStock"}

    seo = d.get("seo", {})
    seo_desc = seo.get("descricao") or plain(d["hero"].get("descricao"))
    if len(seo_desc) > 160:
        avisos.append(f"seo.descricao com {len(seo_desc)} caracteres (ideal até 160)")
    for a, b in (("texto_claro", "noite"), ("texto_claro", "noite_2"), ("tinta", "lava"), ("tinta", "papel"), ("vermelho", "papel")):
        r = contraste(c[a], c[b])
        if r < 4.5: avisos.append(f"contraste baixo: {a} sobre {b} = {r:.2f}")
    if contraste("#FFFFFF", c["azul"]) < 4.5:
        avisos.append(f"contraste do texto branco sobre azul = {contraste('#FFFFFF', c['azul']):.2f} (ok só para texto grande)")

    semente = sum(map(ord, d["slug"]))
    ctx = {
        "previa": previa, "url": url, "ano": d.get("ano") or datetime.date.today().year,
        "seo": {"titulo": seo.get("titulo") or f"{titulo} · {livro['autor']}", "descricao": seo_desc}, "og_imagem": og,
        "c": c, "motivos": motivos,
        "fontes_url": Markup("&".join(FONTES_EXTRA[f]["google"] for f in dict.fromkeys((ft, fx)))),
        "fonte_titulo": Markup(FONTES_EXTRA[ft]["css"]), "fonte_texto": Markup(FONTES_EXTRA[fx]["css"]),
        "livro": {**livro, "titulo": titulo, "titulo_completo": plain(livro.get("titulo_completo") or titulo)},
        "jsonld": Markup(json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")),
        "instagram": instagram,
        "compra": {"principal": d["compra"]["principal"], "outros": d["compra"].get("outros", []),
                   "texto_botao": d["compra"].get("texto_botao", "Garanta o seu exemplar")},
        "hero": {"tagline": rich(d["hero"]["tagline"]), "descricao": rich(d["hero"].get("descricao")), "imagem": hero_img},
        "pergunta": rich(d.get("pergunta")),
        "sinopse": {"titulo": rich(d["sinopse"]["titulo"]), "paragrafos": [rich(x) for x in d["sinopse"]["paragrafos"]],
                    "destaque": ({"texto": rich(d["sinopse"]["destaque"]["texto"]), "referencia": d["sinopse"]["destaque"].get("referencia")}
                                 if d["sinopse"].get("destaque") else None)},
        "personagens": pers,
        "diferenciais": {"titulo": rich(d["diferenciais"]["titulo"]),
                         "itens": [{"titulo": rich(i["titulo"]), "texto": rich(i["texto"])} for i in d["diferenciais"]["itens"]]},
        "cores_itens": [c["lava"], c["vermelho"], c["portal"]],
        "trecho": ({"texto": rich(d["trecho"]["texto"]), "referencia": d["trecho"].get("referencia") or titulo}
                   if d.get("trecho", {}).get("texto") else None),
        "bio": {"rotulo": d["bio"].get("rotulo", "Sobre o autor"), "nome": d["bio"]["nome"], "foto": bio_img,
                "paragrafos": [rich(x) for x in d["bio"]["paragrafos"]]},
        "final": {"titulo": rich(d["final"]["titulo"]), "texto": rich(d["final"]["texto"]), "fecho": rich(d["final"].get("fecho")), "imagem": fin_img},
        "rach_hero": svg_rachaduras(semente, 600, 700, "radial"),
        "rach_borda": svg_rachaduras(semente + 1, 1400, 120, "borda", "rachaduras borda"),
    }
    env = Environment(loader=FileSystemLoader(AQUI / "template"), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    (out / "index.html").write_text(env.get_template("livro-grafico.html.j2").render(**ctx), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if previa else "User-agent: *\nAllow: /\n", encoding="utf-8")
    total = sum(x.stat().st_size for x in out.rglob("*") if x.is_file())
    print(f"OK  {out}  ({total / 1024:.0f} KB)")
    for a in avisos:
        print("AVISO", a)
    return out


# ================== modelo "infantil" ==================
FONTES_INFANTIL = {
    "Grandstander": {"google": "family=Grandstander:wght@700;800", "css": '"Grandstander", "Comic Sans MS", system-ui, sans-serif'},
    "Baloo 2": {"google": "family=Baloo+2:wght@700;800", "css": '"Baloo 2", system-ui, sans-serif'},
    "Fredoka": {"google": "family=Fredoka:wght@600;700", "css": '"Fredoka", system-ui, sans-serif'},
    "Sniglet": {"google": "family=Sniglet:wght@400;800", "css": '"Sniglet", system-ui, sans-serif'},
    "Nunito": {"google": "family=Nunito:ital,wght@0,400;0,600;0,700;0,800;1,400", "css": '"Nunito", system-ui, -apple-system, "Segoe UI", Arial, sans-serif'},
    "Quicksand": {"google": "family=Quicksand:wght@400;600;700", "css": '"Quicksand", system-ui, sans-serif'},
}

# Ícones de traço (32x32) para os cards de motivos. Escolha um por item no lp.json ("icone").
ICONES = {
    "coracao": '<path d="M16 27s-11-6.6-11-14.2A6 6 0 0 1 16 9.4a6 6 0 0 1 11 3.4C27 20.4 16 27 16 27z"/>',
    "estrela": '<path d="M16 4.5l3.4 7.1 7.8 1-5.7 5.4 1.4 7.7L16 22l-6.9 3.7 1.4-7.7-5.7-5.4 7.8-1z"/>',
    "livro": '<path d="M16 9c-3-2.4-7-3-11-2v17c4-1 8-.4 11 2 3-2.4 7-3 11-2V7c-4-1-8-.4-11 2zM16 9v17"/>',
    "folha": '<path d="M7 25C7 13 14 6 26 6c0 12-7 19-19 19zM7 25l10-10"/>',
    "casa": '<path d="M5 15L16 6l11 9M8 13v13h16V13M13 26v-7h6v7"/>',
    "sol": '<circle cx="16" cy="16" r="5.5"/><path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.8 6.8l2.8 2.8M22.4 22.4l2.8 2.8M6.8 25.2l2.8-2.8M22.4 9.6l2.8-2.8"/>',
    "balao": '<path d="M6 7h20v13H14l-6 5v-5H6z"/><path d="M11 13.5h.01M16 13.5h.01M21 13.5h.01"/>',
    "patinha": '<path d="M16 17c-4 0-7 4-7 7 0 2 2 3 4 2.5s4-.6 6 0S23 26 23 24c0-3-3-7-7-7z"/><circle cx="8" cy="12" r="2.4"/><circle cx="13" cy="7.5" r="2.4"/><circle cx="19" cy="7.5" r="2.4"/><circle cx="24" cy="12" r="2.4"/>',
    "lapis": '<path d="M21 5l6 6-15 15H6v-6zM18 8l6 6"/>',
    "lupa": '<circle cx="14" cy="14" r="8"/><path d="M20 20l7 7"/>',
}

# Estampas (padrões repetidos que lembram a capa), desenhadas em SVG na cor "sol_2".
ESTAMPAS = {
    "coracoes": (120, '<path transform="translate({x} {y}) rotate({r}) scale({s})" d="M0 9.5S-11 3-11-4.4A5.6 5.6 0 0 1 0-7.6a5.6 5.6 0 0 1 11 3.2C11 3 0 9.5 0 9.5z"/>',
                 [(22, 24, -14, 1.1), (68, 30, 12, .85), (44, 70, 6, 1.0), (88, 78, -10, .75), (6, 74, 18, .8)]),
    "estrelas": (96, '<path transform="translate({x} {y}) rotate({r}) scale({s})" d="M0-10l2.9 6 6.6.9-4.8 4.6 1.2 6.5L0 4.9l-5.9 3.1 1.2-6.5-4.8-4.6 6.6-.9z"/>',
                 [(20, 22, -8, 1.0), (70, 34, 14, .8), (42, 74, 0, .9), (88, 82, -16, .7)]),
    "bolinhas": (64, '<circle transform="translate({x} {y}) scale({s})" r="5"/>',
                 [(16, 16, 0, 1.0), (48, 48, 0, .7)]),
}


def estampa_css(nome, cor):
    if not nome or nome == "nenhuma":
        return "none", 80
    if nome not in ESTAMPAS:
        raise SystemExit(f"estampa inválida: {nome}. Use uma de: {', '.join(ESTAMPAS)}, nenhuma")
    tam, forma, pontos = ESTAMPAS[nome]
    k = tam / 100
    corpo = "".join(forma.format(x=round(x * k, 1), y=round(y * k, 1), r=r, s=s) for x, y, r, s in pontos)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" height="{tam}" viewBox="0 0 {tam} {tam}"><g fill="{cor}">{corpo}</g></svg>'
    from urllib.parse import quote
    return Markup(f'url("data:image/svg+xml,{quote(svg)}")'), tam


def montar_infantil(d, base, previa, saida, url_base):
    for k in ["slug", "subdominio", "livro.titulo", "livro.autor", "compra.principal.url", "hero.imagem", "hero.tagline",
              "hero.descricao", "sinopse.titulo", "sinopse.paragrafos", "diferenciais.titulo", "diferenciais.itens",
              "bio.nome", "bio.paragrafos", "final.titulo", "final.texto", "final.imagem", "tema.cores"]:
        obrigatorio(d, k)
    if not 2 <= len(d["diferenciais"]["itens"]) <= 4:
        raise SystemExit("diferenciais.itens precisa ter de 2 a 4 itens")
    for i in d["diferenciais"]["itens"]:
        if i.get("icone", "coracao") not in ICONES:
            raise SystemExit(f"ícone inválido: {i.get('icone')}. Use um de: {', '.join(ICONES)}")
    avisos = []
    out = Path(saida or AQUI / "dist").resolve() / d["slug"]
    if out.exists():
        shutil.rmtree(out)
    img_dir = out / "img"
    img_dir.mkdir(parents=True)
    livro = d["livro"]
    titulo = plain(livro["titulo"])

    c = dict(d["tema"]["cores"])
    for k in ("papel", "creme", "sol", "sol_2", "tinta", "destaque", "profundo", "texto_claro"):
        if not c.get(k):
            raise SystemExit(f"Cor obrigatória ausente em tema.cores: {k}")
    c.setdefault("botao", c["destaque"])
    c.setdefault("botao_texto", "#FFFFFF")
    c.setdefault("acento", c["destaque"])
    c.setdefault("rodape", escurecer(c["profundo"], .25))
    txt = CLARO_FIXO if contraste(CLARO_FIXO, c["rodape"]) >= contraste(ESCURO_FIXO, c["rodape"]) else ESCURO_FIXO
    c["rodape_texto"], c["rodape_texto_claro"] = txt, txt == CLARO_FIXO
    for a, b, m in (("tinta", "papel", 4.5), ("tinta", "creme", 4.5), ("tinta", "sol", 4.5), ("botao_texto", "botao", 4.5),
                    ("texto_claro", "profundo", 4.5), ("sol", "profundo", 3), ("destaque", "papel", 3), ("destaque", "creme", 3),
                    ("destaque", "sol", 3), ("rodape_texto", "rodape", 4.5)):
        r = contraste(c[a], c[b])
        if r < m:
            avisos.append(f"contraste baixo: {a} sobre {b} = {r:.2f} (mínimo {m})")

    ft, fx = d["tema"].get("fonte_titulo", "Grandstander"), d["tema"].get("fonte_texto", "Nunito")
    for f in (ft, fx):
        if f not in FONTES_INFANTIL:
            raise SystemExit(f"fonte inválida: {f}. Use uma de: {', '.join(FONTES_INFANTIL)}")
    estampa, estampa_tam = estampa_css(d["tema"].get("estampa", "coracoes"), c["sol_2"])

    def imagem(chave, nome, alt, larguras=LARGURAS):
        return processar_imagem(base / chave, nome, img_dir, alt, larguras)

    hero_img = imagem(d["hero"]["imagem"], "livro", d["hero"].get("alt") or f"Livro {titulo}, de {livro['autor']}", (520, 960))
    fin_img = imagem(d["final"]["imagem"], "final", d["final"].get("alt", ""), (480, 940))
    sin_img = imagem(d["sinopse"]["imagem"], "historia", d["sinopse"].get("alt", ""), (480, 900)) if d["sinopse"].get("imagem") else None
    bio_img = None
    if d["bio"].get("foto"):
        f = ImageOps.exif_transpose(Image.open(base / d["bio"]["foto"])).convert("RGB")
        lado = min(f.size)
        ImageOps.fit(f, (lado, lado), Image.LANCZOS, centering=(.5, .4)).save(img_dir / "_autor.jpg", quality=92)
        bio_img = processar_imagem(img_dir / "_autor.jpg", "autor", img_dir, livro["autor"], (320, 640))
        (img_dir / "_autor.jpg").unlink()

    galeria = None
    if d.get("galeria", {}).get("itens"):
        g = d["galeria"]
        if not 2 <= len(g["itens"]) <= 4:
            raise SystemExit("galeria.itens precisa ter de 2 a 4 ilustrações")
        galeria = {"titulo": rich(g.get("titulo", "Espie as páginas")), "intro": rich(g.get("intro")),
                   "itens": [{"imagem": imagem(i["imagem"], f"pagina-{n}", i.get("alt") or plain(i.get("legenda")), (420, 820)),
                              "legenda": rich(i.get("legenda"))} for n, i in enumerate(g["itens"], 1)]}

    trecho = None
    if d.get("trecho", {}).get("texto"):
        t = d["trecho"]
        trecho = {"texto": rich(t["texto"]), "referencia": t.get("referencia") or titulo,
                  "imagem": imagem(t["imagem"], "trecho", t.get("alt", ""), (420, 800)) if t.get("imagem") else None}

    divisor = None
    if d["tema"].get("divisor"):
        dv = Image.open(base / d["tema"]["divisor"]).convert("RGBA")
        dv.thumbnail((520, 520), Image.LANCZOS)
        dv.save(img_dir / "divisor.webp", "WEBP", quality=90)
        divisor = {"arquivo": "divisor.webp", "w": dv.width, "h": dv.height}

    shutil.copy(AQUI / "assets" / "logo-global.png", img_dir / "logo-global.png")
    instagram = None
    if d.get("instagram", {}).get("usuario"):
        u = d["instagram"]["usuario"].lstrip("@")
        instagram = {"usuario": u, "url": d["instagram"].get("url") or f"https://www.instagram.com/{u}/",
                     "rotulo": d["instagram"].get("rotulo", "Siga a autora")}

    og = og_grafico(c["creme"], base / d["hero"]["imagem"], img_dir) if hero_img["ext"] == "png" else og_imagem(base / d["hero"]["imagem"], img_dir)
    favicon(c["destaque"], out)
    url = url_base or f"https://{d['subdominio']}.bibliomarket.com.br/"

    jsonld = {"@context": "https://schema.org", "@type": "Book", "name": titulo,
              "author": {"@type": "Person", "name": livro["autor"]}, "inLanguage": "pt-BR", "url": url,
              "image": f"{url}img/{og}", "description": plain(d["hero"]["descricao"]), "audience": {"@type": "PeopleAudience", "audienceType": "Crianças"}}
    if livro.get("ilustrador"): jsonld["illustrator"] = {"@type": "Person", "name": livro["ilustrador"]}
    if livro.get("isbn"): jsonld["isbn"] = livro["isbn"]
    jsonld["offers"] = {"@type": "Offer", "url": d["compra"]["principal"]["url"], "availability": "https://schema.org/InStock"}

    seo = d.get("seo", {})
    seo_desc = seo.get("descricao") or plain(d["hero"]["descricao"])
    if len(seo_desc) > 160:
        avisos.append(f"seo.descricao com {len(seo_desc)} caracteres (ideal até 160)")

    ctx = {
        "previa": previa, "url": url, "ano": d.get("ano") or datetime.date.today().year,
        "seo": {"titulo": seo.get("titulo") or f"{titulo} · {livro['autor']}", "descricao": seo_desc}, "og_imagem": og,
        "c": c, "estampa": estampa, "estampa_tam": estampa_tam, "semente": sum(map(ord, d["slug"])) % 97,
        "icones": {k: Markup(v) for k, v in ICONES.items()},
        "fontes_url": Markup("&".join(FONTES_INFANTIL[f]["google"] for f in dict.fromkeys((ft, fx)))),
        "fonte_titulo": Markup(FONTES_INFANTIL[ft]["css"]), "fonte_texto": Markup(FONTES_INFANTIL[fx]["css"]),
        "livro": {**livro, "titulo": titulo},
        "jsonld": Markup(json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")),
        "instagram": instagram, "divisor": divisor,
        "compra": {"principal": d["compra"]["principal"], "outros": d["compra"].get("outros", []),
                   "texto_botao": d["compra"].get("texto_botao", "Garanta o seu exemplar"),
                   "texto_topo": d["compra"].get("texto_topo", "Comprar")},
        "hero": {"tagline": rich(d["hero"]["tagline"]), "descricao": rich(d["hero"]["descricao"]), "imagem": hero_img},
        "sinopse": {"titulo": rich(d["sinopse"]["titulo"]), "paragrafos": [rich(x) for x in d["sinopse"]["paragrafos"]], "imagem": sin_img},
        "galeria": galeria,
        "diferenciais": {"titulo": rich(d["diferenciais"]["titulo"]),
                         "itens": [{"titulo": rich(i["titulo"]), "texto": rich(i["texto"]), "icone": i.get("icone", "coracao")}
                                   for i in d["diferenciais"]["itens"]]},
        "trecho": trecho,
        "bio": {"rotulo": d["bio"].get("rotulo", "Sobre a autora"), "nome": d["bio"]["nome"], "foto": bio_img,
                "paragrafos": [rich(x) for x in d["bio"]["paragrafos"]]},
        "final": {"titulo": rich(d["final"]["titulo"]), "texto": rich(d["final"]["texto"]), "fecho": rich(d["final"].get("fecho")), "imagem": fin_img},
    }
    env = Environment(loader=FileSystemLoader(AQUI / "template"), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    (out / "index.html").write_text(env.get_template("infantil.html.j2").render(**ctx), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if previa else "User-agent: *\nAllow: /\n", encoding="utf-8")
    total = sum(x.stat().st_size for x in out.rglob("*") if x.is_file())
    print(f"OK  {out}  ({total / 1024:.0f} KB)")
    for a in avisos:
        print("AVISO", a)
    return out


MODELOS = {
    "livro-unico": "Livro único, linguagem editorial (clara, serifada; adultos, memórias, romance, não ficção, poesia)",
    "livro-grafico": "Livro único, linguagem gráfica (escura, de impacto; fantasia, aventura, infantojuvenil com ilustração forte)",
    "infantil": "Livro único infantil (até ~10 anos; ilustrado): claro, arredondado, aquarela, páginas do livro e motivos para ler junto",
}


if __name__ == "__main__":
    if "--modelos" in sys.argv:
        print(json.dumps(MODELOS, ensure_ascii=False, indent=2)); sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("lp_json")
    ap.add_argument("--previa", action="store_true")
    ap.add_argument("--saida")
    ap.add_argument("--url", help="URL final da página (padrão: https://<subdominio>.bibliomarket.com.br/)")
    a = ap.parse_args()
    montar(a.lp_json, a.previa, a.saida, a.url)
