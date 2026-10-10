#!/usr/bin/env python3
"""Guarda e recupera o projeto de uma LP (lp.json, imagens-fonte, faces da capa, notas) no GitHub.

  python3 projeto.py salvar <pasta-do-projeto> <slug>     → branch projeto/<slug> (sobrescreve)
  python3 projeto.py baixar <slug> <pasta-destino>        → traz o projeto de volta (para Ajuste ou republicar)
  python3 projeto.py existe <slug>                        → imprime "sim" ou "não"

As sessões não guardam arquivos entre uma rodada e outra: tudo o que a LP precisa para ser
gerada de novo (sem baixar o Drive outra vez) vai para esse branch. Não guarde aqui o texto
inteiro do livro nem PDFs grandes: só o que a LP usa, mais as notas (notas.md).
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
IGNORAR = shutil.ignore_patterns("dist", "_prints*", "*.pdf", "livro.md", "__pycache__", ".git")


def git(*args, cwd, ok=False):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode and not ok:
        sys.exit(f"git {' '.join(args)} falhou:\n{r.stderr.strip()}")
    return r


def remoto():
    return git("remote", "get-url", "origin", cwd=RAIZ).stdout.strip()


def salvar(pasta, slug):
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(Path(pasta), tmp, dirs_exist_ok=True, ignore=IGNORAR)
    grandes = [p for p in tmp.rglob("*") if p.is_file() and p.stat().st_size > 8 * 1024 * 1024]
    if grandes:
        sys.exit(f"Arquivos grandes demais para o projeto (máx. 8 MB): {[str(p.name) for p in grandes]}")
    git("init", "-q", "-b", "p", cwd=tmp)
    git("config", "user.name", "Automação LPs Global", cwd=tmp); git("config", "user.email", "noreply@assessoriaglobal.com.br", cwd=tmp)
    git("add", "-A", cwd=tmp); git("commit", "-q", "-m", f"projeto {slug}", cwd=tmp)
    git("push", "-q", "--force", remoto(), f"p:refs/heads/projeto/{slug}", cwd=tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"OK projeto/{slug} salvo")


def baixar(slug, destino):
    destino = Path(destino)
    if destino.exists() and any(destino.iterdir()):
        sys.exit(f"{destino} já tem arquivos; use uma pasta vazia.")
    r = git("clone", "-q", "--depth", "1", "--branch", f"projeto/{slug}", remoto(), str(destino), cwd=RAIZ, ok=True)
    if r.returncode:
        sys.exit(f"Projeto {slug} não encontrado no GitHub.")
    shutil.rmtree(destino / ".git", ignore_errors=True)
    print(f"OK projeto/{slug} em {destino}")


def existe(slug):
    r = git("ls-remote", "--heads", remoto(), f"projeto/{slug}", cwd=RAIZ)
    print("sim" if r.stdout.strip() else "não")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["salvar"] and len(a) == 3: salvar(a[1], a[2])
    elif a[:1] == ["baixar"] and len(a) == 3: baixar(a[1], a[2])
    elif a[:1] == ["existe"] and len(a) == 2: existe(a[1])
    else: sys.exit(__doc__)
