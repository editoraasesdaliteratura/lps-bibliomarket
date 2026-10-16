#!/usr/bin/env python3
"""Renderiza o mockup 3D de um livro (brochura) em PNG.

  python3 mockup/render.py <pasta-faces> <saida.png> [--cena pe|frente|par] [--tam 2000] [--s 0.9] [--giro 22] [--fundo]

<pasta-faces> é a saída de `ferramentas/capa.py faces`: frente.jpg, lombada.jpg, verso.jpg e faces.json
(com W, H, T). Sem lombada medida (faces.json com "lombada": false) só a cena "frente" é permitida:
nunca invente a espessura da lombada.
Por padrão o fundo é transparente (para compor na LP); --fundo deixa um cinza claro (para conferir).
"""
import argparse, asyncio, functools, http.server, json, shutil, socket, sys, tempfile, threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def porta_livre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


async def render(pasta, saida, cena, tam, s, fundo, giro=None):
    from playwright.async_api import async_playwright
    meta = json.loads((pasta / "faces.json").read_text())
    if cena != "frente" and not meta.get("lombada"):
        sys.exit("ERRO: esta capa não tem lombada medida (sem capa aberta). Use --cena frente.")
    if cena == "par" and not (pasta / "verso.jpg").exists():
        sys.exit("ERRO: cena 'par' precisa da contracapa (verso.jpg).")
    tmp = Path(tempfile.mkdtemp())
    for f in ("frente.jpg", "lombada.jpg", "verso.jpg"):
        if (pasta / f).exists():
            shutil.copy(pasta / f, tmp / f)
    for f in ("lombada.jpg", "verso.jpg"):  # cena "frente" não mostra essas faces, mas o HTML as referencia
        if not (tmp / f).exists():
            shutil.copy(tmp / "frente.jpg", tmp / f)
    shutil.copy(AQUI / "livro3d.html", tmp / "livro3d.html")

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    porta = porta_livre()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(Q, directory=str(tmp)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    q = f"w={tam}&h={tam}&W={meta['W']}&H={meta['H']}&T={meta.get('T') or meta.get('T_estimada') or round(meta['H'] * .035)}&cena={cena}&s={s}" + (f"&giro={giro}" if giro is not None else "") + ("" if fundo else "&recorte=1")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": tam, "height": tam}, device_scale_factor=1)
        await pg.goto(f"http://127.0.0.1:{porta}/livro3d.html?{q}", wait_until="networkidle")
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=str(saida), omit_background=not fundo)
        await b.close()
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    # corta as sobras transparentes, deixando uma margem para a sombra
    if not fundo:
        from PIL import Image
        im = Image.open(saida).convert("RGBA")
        bb = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if bb:
            m = round(tam * .02)
            im.crop((max(0, bb[0] - m), max(0, bb[1] - m), min(im.width, bb[2] + m), min(im.height, bb[3] + m))).save(saida)
    print("OK", saida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("faces"); ap.add_argument("saida")
    ap.add_argument("--cena", default="pe", choices=["pe", "frente", "par"])
    ap.add_argument("--tam", type=int, default=2000)
    ap.add_argument("--s", type=float, default=None, help="escala do livro na cena (1 = livro com ~74%% da altura; padrão pe 1, frente 1, par .82)")
    ap.add_argument("--fundo", action="store_true")
    ap.add_argument("--giro", type=float, default=None, help="giro do livro em graus (padrão pe 34, frente 24); menor = mais de frente")
    a = ap.parse_args()
    s = a.s or {"pe": 1.0, "frente": 1.0, "par": .82}[a.cena]
    asyncio.run(render(Path(a.faces).resolve(), Path(a.saida).resolve(), a.cena, a.tam, s, a.fundo, a.giro))
