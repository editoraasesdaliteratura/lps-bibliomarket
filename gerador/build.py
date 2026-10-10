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
    if d.get("modelo") == "livro-grafico":
        return montar_grafico(d, base, previa, saida, url_base)
    for c in ["slug", "subdominio", "livro.titulo", "livro.autor", "compra.principal.url",
              "hero.tagline", "hero.descricao", "hero.imagem", "sinopse.titulo", "sinopse.paragrafos",
              "diferenciais.titulo", "diferenciais.itens", "diferenciais.imagem", "bio.nome", "bio.paragrafos",
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
    dif_img = img(d["diferenciais"]["imagem"], d["diferenciais"].get("alt", ""))
    fin_img = img(d["final"]["imagem"], d["final"].get("alt") or f"Livro {titulo}")
    bio_img = img(d["bio"]["foto"], livro["autor"]) if d["bio"].get("foto") else None
    shutil.copy(AQUI / "assets" / "logo-global.png", img_dir / "logo-global.png")

    instagram = None
    if d.get("instagram", {}).get("usuario"):
        ig = d["instagram"]
        usuario = ig["usuario"].lstrip("@")
        foto = None
        if ig.get("foto"):
            im = ImageOps.fit(Image.open(base / ig["foto"]).convert("RGB"), (96, 96), Image.LANCZOS)
            im.save(img_dir / "ig.webp", "WEBP", quality=85)
            foto = "ig.webp"
        instagram = {"usuario": usuario, "url": ig.get("url") or f"https://www.instagram.com/{usuario}/",
                     "foto": foto, "rotulo": ig.get("rotulo", "Siga o autor")}

    og = og_imagem(base / d["hero"]["imagem"], img_dir)
    favicon(cores["destaque"], out)

    url = url_base or f"https://{d['subdominio']}.bibliomarket.com.br/"
    ficha = [x for x in [livro.get("genero"), f"{livro['paginas']} páginas" if livro.get("paginas") else None,
                         livro.get("editora")] if x]

    jsonld = {"@context": "https://schema.org", "@type": "Book", "name": titulo,
              "author": {"@type": "Person", "name": livro["autor"]}, "inLanguage": "pt-BR",
              "url": url, "image": f"{url}img/{og}", "description": plain(d["hero"]["descricao"])}
    if livro.get("isbn"): jsonld["isbn"] = livro["isbn"]
    if livro.get("paginas"): jsonld["numberOfPages"] = int(livro["paginas"])
    if livro.get("editora"): jsonld["publisher"] = {"@type": "Organization", "name": livro["editora"]}
    if livro.get("genero"): jsonld["genre"] = livro["genero"]
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
        "cores": cores, "livro": {**livro, "titulo": titulo}, "ficha": ficha,
        "jsonld": Markup(json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")),
        "instagram": instagram,
        "compra": {"principal": d["compra"]["principal"], "outros": d["compra"].get("outros", []),
                   "texto_botao": d["compra"].get("texto_botao", "Adquira o seu exemplar")},
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
    ficha = [x for x in [livro.get("editora"), f"{livro['paginas']} páginas" if livro.get("paginas") else None] if x]

    jsonld = {"@context": "https://schema.org", "@type": "Book", "name": plain(livro.get("titulo_completo") or titulo),
              "author": {"@type": "Person", "name": livro["autor"]}, "inLanguage": "pt-BR", "url": url,
              "image": f"{url}img/{og}", "description": plain(d["hero"].get("descricao") or d["hero"]["tagline"])}
    for k, v in (("isbn", "isbn"), ("genero", "genre")):
        if livro.get(k): jsonld[v] = livro[k]
    if livro.get("paginas"): jsonld["numberOfPages"] = int(livro["paginas"])
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
        "ficha": ficha, "jsonld": Markup(json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")),
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lp_json")
    ap.add_argument("--previa", action="store_true")
    ap.add_argument("--saida")
    ap.add_argument("--url", help="URL final da página (padrão: https://<subdominio>.bibliomarket.com.br/)")
    a = ap.parse_args()
    montar(a.lp_json, a.previa, a.saida, a.url)
