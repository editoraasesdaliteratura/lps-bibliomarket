#!/usr/bin/env python3
"""Extrai o texto de um livro para escrever a LP.

  python3 texto.py <arquivo.docx|.doc|.pdf|.txt> [--saida livro.md] [--resumo]

- .docx (texto final revisado, o preferido): títulos viram "## ", parágrafos preservados.
- .doc: convertido com pandoc/antiword/libreoffice se existir; senão peça o .docx.
- .pdf (miolo): texto página a página, com marcador "[pág N]".
--resumo imprime só o mapa do livro: total de palavras e os títulos (capítulos) com a posição,
para escolher onde ler (apresentação, orelha, 1º capítulo, um trecho forte).
"""
import argparse, re, shutil, subprocess, sys
from pathlib import Path


def docx_md(caminho):
    import docx
    doc = docx.Document(str(caminho))
    linhas = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        estilo = (p.style.name or "").lower() if p.style is not None else ""
        curto = len(t) < 80 and not t.endswith((".", ",", ";", ":", "!", "?", "…", '"', "”"))
        if "heading" in estilo or "título" in estilo or "titulo" in estilo or "title" in estilo or (
                curto and (t.isupper() or re.match(r"^(cap[ií]tulo|parte|pr[oó]logo|ep[ií]logo|apresenta|pref[aá]cio|introdu)", t, re.I))):
            linhas.append(f"\n## {t}\n")
        else:
            linhas.append(t)
    return "\n\n".join(linhas)


def pdf_md(caminho):
    from pypdf import PdfReader
    r = PdfReader(str(caminho))
    return "\n\n".join(f"[pág {i}]\n{(pg.extract_text() or '').strip()}" for i, pg in enumerate(r.pages, 1))


def doc_md(caminho):
    if shutil.which("pandoc"):
        try:
            return subprocess.run(["pandoc", "-f", "doc", "-t", "plain", str(caminho)], capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            pass
    if shutil.which("antiword"):
        return subprocess.run(["antiword", str(caminho)], capture_output=True, text=True).stdout
    for office in ("soffice", "libreoffice"):
        if shutil.which(office):
            out = Path("/tmp/_doc_conv"); out.mkdir(exist_ok=True)
            subprocess.run([office, "--headless", "--convert-to", "docx", "--outdir", str(out), str(caminho)], capture_output=True)
            alvo = out / (Path(caminho).stem + ".docx")
            if alvo.exists():
                return docx_md(alvo)
    sys.exit("Não consegui ler o .doc aqui. Use read_file_content do Drive (texto) ou peça o .docx/PDF.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo"); ap.add_argument("--saida"); ap.add_argument("--resumo", action="store_true")
    a = ap.parse_args()
    ext = Path(a.arquivo).suffix.lower()
    md = {".docx": docx_md, ".pdf": pdf_md, ".doc": doc_md}.get(ext, lambda c: Path(c).read_text(encoding="utf-8", errors="ignore"))(a.arquivo)
    if a.saida:
        Path(a.saida).write_text(md, encoding="utf-8")
    if a.resumo:
        palavras = len(md.split())
        print(f"{palavras} palavras")
        pos = 0
        for linha in md.splitlines():
            if linha.startswith("## "):
                print(f"  {pos:>7}  {linha[3:]}")
            pos += len(linha.split())
    elif not a.saida:
        print(md)
    else:
        print(f"OK {a.saida} ({len(md.split())} palavras)")


if __name__ == "__main__":
    main()
