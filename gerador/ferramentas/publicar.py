#!/usr/bin/env python3
"""Envia uma LP gerada para o GitHub, num branch só dela, para a Hostinger puxar por Git.

  python3 publicar.py <dist/slug> --branch lp/previa-<slug>    (prévia, em teste-lp.bibliomarket.com.br/<slug>/)
  python3 publicar.py <dist/slug> --branch lp/<slug>           (versão final, no subdomínio do autor/livro)

Cada LP vive num branch órfão (sem histórico do gerador), com só o site e um .htaccess.
Cada envio vira um commit novo em cima do anterior (a Hostinger só sabe avançar com "pull").
Só aceita branches que começam com "lp/" (nunca mexe no main).
Depois do envio, a Hostinger precisa puxar: `hosting_git_deploy-website-repository` (veja a SKILL).
"""
import argparse, shutil, subprocess, sys, tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
HTACCESS = """# Gerado pelo gerador de LPs da Global. Não editar no servidor.
DirectoryIndex index.html
Options -Indexes
RedirectMatch 404 /\\.git
<IfModule mod_headers.c>
  <FilesMatch "\\.(webp|jpg|png|svg|woff2)$">
    Header set Cache-Control "public, max-age=2592000"
  </FilesMatch>
  <FilesMatch "\\.html$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>
"""


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"git {' '.join(args)} falhou:\n{r.stderr.strip()}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta"); ap.add_argument("--branch", required=True); ap.add_argument("--mensagem")
    ap.add_argument("--base", help="(recuperação) commit que a Hostinger tem hoje, quando o branch no GitHub divergiu dele")
    a = ap.parse_args()
    if not a.branch.startswith("lp/"):
        sys.exit("O branch precisa começar com lp/ (o main guarda o gerador e nunca recebe sites).")
    pasta = Path(a.pasta).resolve()
    if not (pasta / "index.html").exists():
        sys.exit(f"{pasta} não tem index.html. Gere a LP antes.")
    remoto = git("remote", "get-url", "origin", cwd=RAIZ)
    tmp = Path(tempfile.mkdtemp())
    git("init", "-q", "-b", "site", cwd=tmp)
    for k, v in (("user.name", "Automação LPs Global"), ("user.email", "noreply@assessoriaglobal.com.br")):
        git("config", k, v, cwd=tmp)
    # Cada versão nova é filha da anterior: a Hostinger só faz "pull" (avanço simples).
    # Nunca reescrever o histórico do branch: o pull no servidor falharia.
    base = a.base
    if not base:
        r = subprocess.run(["git", "ls-remote", "--heads", remoto, a.branch], cwd=tmp, capture_output=True, text=True)
        base = r.stdout.split()[0] if r.stdout.strip() else None
    forcar = bool(a.base)
    if base:
        git("fetch", "-q", "--depth", "1", remoto, base, cwd=tmp)
        git("reset", "-q", "--soft", base, cwd=tmp)
    shutil.copytree(pasta, tmp, dirs_exist_ok=True)
    (tmp / ".htaccess").write_text(HTACCESS, encoding="utf-8")
    # arquivos que saíram da versão nova também saem do branch
    git("add", "-A", cwd=tmp)
    if base:
        atuais = {str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file() and ".git" not in p.parts}
        rastreados = git("ls-files", cwd=tmp).splitlines()
        for f in rastreados:
            if f not in atuais:
                git("rm", "-q", "--cached", f, cwd=tmp)
    if base and not git("status", "--porcelain", cwd=tmp):
        print(f"Sem mudanças: branch {a.branch} já está nesta versão")
        shutil.rmtree(tmp, ignore_errors=True)
        return
    git("commit", "-q", "-m", a.mensagem or f"LP {pasta.name}", cwd=tmp)
    git("push", "-q", *(["--force"] if forcar else []), remoto, f"site:refs/heads/{a.branch}", cwd=tmp)
    sha = git("rev-parse", "--short", "HEAD", cwd=tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"OK branch {a.branch} @ {sha}" + (f" (filho de {base[:7]})" if base else " (primeira versão)"))


if __name__ == "__main__":
    main()
