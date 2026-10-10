#!/usr/bin/env python3
"""Converte o resultado do `download_file_content` (Google Drive) em arquivo de verdade.

  python3 drive.py <resultado> <pasta-ou-arquivo-de-saida>

<resultado> é o arquivo .txt que o conector grava quando o download é grande
(JSON com "content" em base64, "title" e "mimeType"), ou um arquivo só com o base64.
Se a saída for uma pasta, o arquivo ganha o título original. Imprime caminho, tipo e tamanho.
"""
import base64, json, re, sys
from pathlib import Path


def nome_seguro(titulo):
    """Nome sem acentos nem espaços (evita problemas de normalização Unicode no terminal)."""
    import unicodedata
    base = "".join(c for c in unicodedata.normalize("NFD", titulo) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") or "arquivo"


def main(origem, destino):
    bruto = Path(origem).read_text(encoding="utf-8", errors="ignore").strip()
    titulo, tipo = None, None
    if bruto.startswith("{") or bruto.startswith("["):
        d = json.loads(bruto)
        if isinstance(d, list):  # alguns clientes embrulham em [{"type":"text","text":"{...}"}]
            d = json.loads(d[0]["text"])
        conteudo, titulo, tipo = d["content"], d.get("title"), d.get("mimeType")
    else:
        conteudo = bruto
    dados = base64.b64decode(re.sub(r"\s+", "", conteudo))
    dest = Path(destino)
    if dest.is_dir() or str(destino).endswith("/"):
        dest.mkdir(parents=True, exist_ok=True)
        nome = nome_seguro(titulo or "arquivo")
        dest = dest / nome
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(dados)
    print(json.dumps({"arquivo": str(dest), "titulo": titulo, "tipo": tipo, "kb": round(len(dados) / 1024)}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
