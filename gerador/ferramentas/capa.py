#!/usr/bin/env python3
"""Ferramentas de capa para as LPs.

  faces    Separa frente, lombada e contracapa a partir da capa aberta (PDF de gráfica ou imagem)
           e mede a lombada de verdade. Sem capa aberta, gera só a frente (e o mockup fica sem lombada).
             python3 capa.py faces --saida faces/ [--frente frente.jpg] [--aberta aberta.jpg | --pdf-capa capa.pdf]
                                   [--pdf-miolo miolo.pdf] [--paginas 304]
  pdf      Renderiza uma página de PDF (recortada na TrimBox, sem sangria) em JPG.
             python3 capa.py pdf arquivo.pdf saida.jpg [--pagina 1] [--altura 2400] [--sangria]
  paleta   Cores dominantes de uma imagem (JSON) + amostra em PNG para conferir.
             python3 capa.py paleta frente.jpg [--n 8] [--amostra paleta.png]
  recortar Recorta um trecho (personagem, foto do autor na orelha, arte) em PNG.
             python3 capa.py recortar img.jpg x0 y0 x1 y1 saida.png [--rel] [--tirar-fundo '#007EAE' --tol 60] [--circulo]
                                     [--tirar-claro [--cor '#5B3E34']]   (ornamento sobre papel → PNG transparente)

Sempre confira a imagem `conferencia.jpg` que o `faces` grava: ela mostra onde cada parte foi cortada.
"""
import argparse, json, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

PT_MM = 25.4 / 72


# ---------------- PDF ----------------
def caixas_pdf(caminho, pagina=1):
    from pypdf import PdfReader
    p = PdfReader(str(caminho)).pages[pagina - 1]
    mb = [float(x) for x in p.mediabox]
    tb = [float(x) for x in (p.trimbox if "/TrimBox" in p else p.mediabox)]
    return mb, tb


def renderizar_pdf(caminho, pagina=1, altura=2400, sangria=False):
    """Devolve (PIL.Image, mm_por_px). Recorta na TrimBox (área final do livro) salvo --sangria."""
    mb, tb = caixas_pdf(caminho, pagina)
    alvo = mb if sangria else tb
    dpi = altura / ((alvo[3] - alvo[1]) / 72)
    im = None
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(caminho))
        im = pdf[pagina - 1].render(scale=dpi / 72).to_pil().convert("RGB")
    except ImportError:
        tmp = Path("/tmp/_capa_render")
        subprocess.run(["pdftoppm", "-f", str(pagina), "-l", str(pagina), "-r", f"{dpi:.2f}", "-jpeg", "-jpegopt", "quality=95",
                        "-singlefile", str(caminho), str(tmp)], check=True)
        im = Image.open(str(tmp) + ".jpg").convert("RGB")
    esc = im.height / ((mb[3] - mb[1]))  # px por pt
    if not sangria:
        x0 = (tb[0] - mb[0]) * esc; x1 = (tb[2] - mb[0]) * esc
        y0 = (mb[3] - tb[3]) * esc; y1 = (mb[3] - tb[1]) * esc
        im = im.crop((round(x0), round(y0), round(x1), round(y1)))
    return im, PT_MM / esc


def tamanho_mm(caminho, pagina=1):
    _, tb = caixas_pdf(caminho, pagina)
    return (tb[2] - tb[0]) * PT_MM, (tb[3] - tb[1]) * PT_MM


def abrir(caminho):
    c = Path(caminho)
    if c.suffix.lower() == ".pdf":
        im, mmpx = renderizar_pdf(c)
        return im, mmpx
    return ImageOps.exif_transpose(Image.open(c)).convert("RGB"), None


# ---------------- faces ----------------
def espessura_estimada(altura_px, paginas):
    """Só para o bloco de páginas da cena 'frente' (a lombada nunca é inventada)."""
    proporcao = ((paginas * .06 + .6) / 230) if paginas else .035
    return max(4, round(altura_px * min(.09, max(.012, proporcao))))


def localizar_frente(aberta, frente, largura_frente):
    """Procura a capa da frente dentro da capa aberta (correlação). Devolve (x, confiança)."""
    import cv2
    h = 600
    esc = h / aberta.height
    A = cv2.cvtColor(np.array(aberta.resize((round(aberta.width * esc), h), Image.LANCZOS)), cv2.COLOR_RGB2GRAY)
    wf = round(largura_frente * esc)
    F = cv2.cvtColor(np.array(frente.resize((wf, h), Image.LANCZOS)), cv2.COLOR_RGB2GRAY)
    # ignora uma faixa nas bordas da frente (sangria e vinco variam entre arquivos)
    m = max(2, round(wf * .04))
    r = cv2.matchTemplate(A, F[:, m:wf - m], cv2.TM_CCOEFF_NORMED)[0]
    x = int(np.argmax(r))
    return round((x - m) / esc), float(r[x])


def faces(a):
    out = Path(a.saida); out.mkdir(parents=True, exist_ok=True)
    meta = {"lombada": False, "avisos": []}
    frente_img = abrir(a.frente)[0] if a.frente else None

    if not (a.aberta or a.pdf_capa):
        if frente_img is None:
            sys.exit("ERRO: informe ao menos --frente ou a capa aberta.")
        frente_img.save(out / "frente.jpg", quality=92)
        meta.update(W=frente_img.width, H=frente_img.height, T=None, metodo="só frente",
                    T_estimada=espessura_estimada(frente_img.height, a.paginas))
        meta["avisos"].append("Sem capa aberta: o mockup não pode mostrar a lombada (use a cena 'frente').")
        (out / "faces.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        print(json.dumps(meta, ensure_ascii=False, indent=2)); return

    if a.pdf_capa:
        aberta, mmpx = renderizar_pdf(a.pdf_capa, altura=2400)
        meta["metodo"] = "PDF da capa (TrimBox)"
    else:
        aberta, mmpx = abrir(a.aberta)
        meta["metodo"] = "imagem da capa aberta"
    Wa, Ha = aberta.size

    # proporção da frente: miolo (exata) > imagem da frente > formato padrão
    if a.pdf_miolo:
        fw, fh = tamanho_mm(a.pdf_miolo)
        prop, origem = fw / fh, f"miolo {fw:.0f}×{fh:.0f} mm"
    elif frente_img is not None:
        prop, origem = frente_img.width / frente_img.height, "imagem da frente"
    else:
        sys.exit("ERRO: para separar a capa aberta preciso da frente (--frente) ou do miolo (--pdf-miolo).")
    F = round(prop * Ha)
    meta["proporcao_origem"] = origem

    if frente_img is not None:
        xf, conf = localizar_frente(aberta, frente_img, F)
        meta["confianca"] = round(conf, 3)
        if conf < .55:
            meta["avisos"].append(f"A frente foi achada com confiança baixa ({conf:.2f}). Confira a conferência.")
    else:  # sem imagem da frente: supõe sem orelhas, frente encostada na direita
        xf, conf = Wa - F, None
        if Wa - 2 * F > .15 * F:
            meta["avisos"].append("Sobra largura demais para ser só lombada (orelhas?). Sem a imagem da frente não dá para medir.")
            xf = None

    if xf is not None:
        xf = max(0, min(Wa - F, xf))
        orelha = max(0, Wa - (xf + F))
        if orelha < .02 * F:
            orelha = 0
        lomb = xf - orelha - F
        meta.update(orelha_px=orelha, lombada_px=lomb)
        if lomb < .004 * Ha or lomb > .12 * Ha:
            meta["avisos"].append(f"Lombada medida fora do plausível ({lomb}px para {Ha}px de altura). Mockup sem lombada.")
        else:
            meta["lombada"] = True
        frente = aberta.crop((xf, 0, xf + F, Ha))
        frente.save(out / "frente.jpg", quality=92)
        if meta["lombada"]:
            aberta.crop((xf - lomb, 0, xf, Ha)).save(out / "lombada.jpg", quality=92)
            aberta.crop((orelha, 0, orelha + F, Ha)).save(out / "verso.jpg", quality=92)
        meta.update(W=F, H=Ha, T=lomb if meta["lombada"] else None,
                    T_estimada=lomb if meta["lombada"] else espessura_estimada(Ha, a.paginas))
        if mmpx:
            meta["mm"] = {"frente": round(F * mmpx, 1), "altura": round(Ha * mmpx, 1),
                          "lombada": round(lomb * mmpx, 1), "orelha": round(orelha * mmpx, 1)}
            if a.paginas and meta["lombada"]:
                esperado = a.paginas * .05 + .6
                meta["mm"]["lombada_esperada_papel_75g"] = round(esperado, 1)
                if abs(lomb * mmpx - esperado) > max(2.5, esperado * .45):
                    meta["avisos"].append("Lombada medida bem diferente da esperada pelo nº de páginas. Confira.")
        # conferência visual
        conf_img = aberta.copy()
        d = ImageDraw.Draw(conf_img)
        for x, cor in ((orelha, "#00E5FF"), (orelha + F, "#FF2D95"), (xf, "#FF2D95"), (xf + F, "#00E5FF")):
            d.line([(x, 0), (x, Ha)], fill=cor, width=max(3, Ha // 300))
        conf_img.thumbnail((1800, 1800))
        conf_img.save(out / "conferencia.jpg", quality=85)
    else:
        frente_img.save(out / "frente.jpg", quality=92)
        meta.update(W=frente_img.width, H=frente_img.height, T=None, T_estimada=espessura_estimada(frente_img.height, a.paginas))

    (out / "faces.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2))


# ---------------- paleta ----------------
def _hex(c):
    return "#%02X%02X%02X" % tuple(int(v) for v in c)


def _lum(c):
    c = [v / 255 for v in c]
    c = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def paleta(a):
    from sklearn.cluster import KMeans
    im = abrir(a.imagem)[0]
    im.thumbnail((240, 240))
    px = np.array(im).reshape(-1, 3).astype(float)
    km = KMeans(n_clusters=a.n, n_init=6, random_state=1).fit(px)
    cont = np.bincount(km.labels_, minlength=a.n) / len(px)
    cores = []
    for c, p in sorted(zip(km.cluster_centers_, cont), key=lambda t: -t[1]):
        r, g, b = c / 255
        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0 if mx == 0 else (mx - mn) / mx
        cores.append({"hex": _hex(c), "peso": round(float(p), 3), "luminancia": round(_lum(c), 3), "saturacao": round(sat, 2)})
    if a.amostra:
        sw = Image.new("RGB", (120 * len(cores), 150), "white")
        d = ImageDraw.Draw(sw)
        for i, c in enumerate(cores):
            d.rectangle([i * 120, 0, i * 120 + 119, 110], fill=c["hex"])
            d.text((i * 120 + 6, 118), f'{c["hex"]} {c["peso"]:.0%}', fill="black")
        sw.save(a.amostra)
    print(json.dumps(cores, ensure_ascii=False, indent=2))


# ---------------- recortar ----------------
def recortar(a):
    im = abrir(a.imagem)[0]
    x0, y0, x1, y1 = a.x0, a.y0, a.x1, a.y1
    if a.rel:
        x0, x1 = x0 * im.width, x1 * im.width
        y0, y1 = y0 * im.height, y1 * im.height
    r = im.crop((round(x0), round(y0), round(x1), round(y1))).convert("RGBA")
    if a.tirar_fundo:
        alvo = np.array([int(a.tirar_fundo.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], float)
        arr = np.array(r).astype(float)
        dist = np.sqrt(((arr[..., :3] - alvo) ** 2).sum(-1))
        alfa = np.clip((dist - a.tol * .6) / (a.tol * .4), 0, 1) * 255
        arr[..., 3] = np.minimum(arr[..., 3], alfa)
        r = Image.fromarray(arr.astype("uint8"), "RGBA")
    if a.tirar_claro:
        # ornamento impresso sobre papel/fundo claro: o fundo vira transparente pela luminância
        arr = np.array(r).astype(float)
        lum = arr[..., :3] @ np.array([.299, .587, .114])
        fundo = np.percentile(lum, 85)
        tinta = np.percentile(lum, 3)
        alfa = np.clip((fundo - lum) / max(1, (fundo - tinta)) * 1.6 - .38, 0, 1) ** .8
        # cor única da tinta (mediana dos pixels mais escuros) para um traço limpo
        escuros = arr[..., :3][lum < np.percentile(lum, 10)]
        cor = np.median(escuros, axis=0) if a.cor is None else np.array([int(a.cor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], float)
        # tira manchas soltas do papel: só ficam as partes conectadas grandes do traço
        import cv2
        mascara = (alfa > .25).astype("uint8")
        n, rotulos, est, _ = cv2.connectedComponentsWithStats(mascara, 8)
        minimo = mascara.size * .0015
        manter = np.zeros(n, bool); manter[1:] = est[1:, cv2.CC_STAT_AREA] >= minimo
        perto = cv2.dilate((manter[rotulos]).astype("uint8"), np.ones((5, 5), "uint8")) > 0
        alfa = np.where(perto, alfa, 0)
        # esmaece as bordas do recorte: nenhuma aresta reta aparece na página
        h, w = alfa.shape
        fy = np.clip(np.minimum(np.arange(h), np.arange(h)[::-1]) / (h * .06), 0, 1)
        fx = np.clip(np.minimum(np.arange(w), np.arange(w)[::-1]) / (w * .06), 0, 1)
        alfa = alfa * np.outer(fy, fx)
        arr[..., :3] = cor
        arr[..., 3] = alfa * 255
        r = Image.fromarray(arr.astype("uint8"), "RGBA")
        bb = r.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
        if bb:
            r = r.crop(bb)
    if a.circulo:
        lado = min(r.size)
        r = ImageOps.fit(r, (lado, lado))
        m = Image.new("L", (lado, lado), 0); ImageDraw.Draw(m).ellipse([0, 0, lado, lado], fill=255)
        r.putalpha(Image.fromarray(np.minimum(np.array(r.getchannel("A")), np.array(m))))
    if Path(a.saida).suffix.lower() in (".jpg", ".jpeg"):
        r = r.convert("RGB")
        r.save(a.saida, quality=92)
    else:
        r.save(a.saida)
    print("OK", a.saida, r.size)


def pdf_cmd(a):
    im, mmpx = renderizar_pdf(a.arquivo, a.pagina, a.altura, a.sangria)
    im.save(a.saida, quality=92)
    print(json.dumps({"saida": a.saida, "px": im.size, "mm": [round(im.width * mmpx, 1), round(im.height * mmpx, 1)]}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("faces"); p.add_argument("--saida", required=True); p.add_argument("--frente"); p.add_argument("--aberta")
    p.add_argument("--pdf-capa"); p.add_argument("--pdf-miolo"); p.add_argument("--paginas", type=int); p.set_defaults(f=faces)
    p = sp.add_parser("pdf"); p.add_argument("arquivo"); p.add_argument("saida"); p.add_argument("--pagina", type=int, default=1)
    p.add_argument("--altura", type=int, default=2400); p.add_argument("--sangria", action="store_true"); p.set_defaults(f=pdf_cmd)
    p = sp.add_parser("paleta"); p.add_argument("imagem"); p.add_argument("--n", type=int, default=8); p.add_argument("--amostra"); p.set_defaults(f=paleta)
    p = sp.add_parser("recortar"); p.add_argument("imagem")
    for k in ("x0", "y0", "x1", "y1"): p.add_argument(k, type=float)
    p.add_argument("saida"); p.add_argument("--rel", action="store_true"); p.add_argument("--tirar-fundo"); p.add_argument("--tol", type=float, default=60)
    p.add_argument("--circulo", action="store_true")
    p.add_argument("--tirar-claro", action="store_true", help="ornamento impresso sobre fundo claro: fundo transparente, traço numa cor só")
    p.add_argument("--cor", help="cor do traço com --tirar-claro (padrão: a da própria tinta)")
    p.set_defaults(f=recortar)
    a = ap.parse_args(); a.f(a)
