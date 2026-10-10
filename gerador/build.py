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
def processar_imagem(origem, nome, destino, alt=""):
    im = ImageOps.exif_transpose(Image.open(origem)).convert("RGB")
    w, h = im.size
    for lw in LARGURAS:
        alvo = im if w <= lw else im.resize((lw, round(h * lw / w)), Image.LANCZOS)
        alvo.save(destino / f"{nome}-{lw}.webp", "WEBP", quality=82, method=6)
        if lw == LARGURAS[-1]:
            alvo.save(destino / f"{nome}-{lw}.jpg", "JPEG", quality=84, optimize=True, progressive=True)
    fw = min(w, LARGURAS[-1])
    return {"arquivo": nome, "w": fw, "h": round(h * fw / w), "alt": alt}


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
        "fonte": {"google": f["google"], "peso": f["peso"], "css": f'"{fonte_nome}", {f["fallback"]}'},
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lp_json")
    ap.add_argument("--previa", action="store_true")
    ap.add_argument("--saida")
    ap.add_argument("--url", help="URL final da página (padrão: https://<subdominio>.bibliomarket.com.br/)")
    a = ap.parse_args()
    montar(a.lp_json, a.previa, a.saida, a.url)
