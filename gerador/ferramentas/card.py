#!/usr/bin/env python3
"""Lê um card do quadro "LP • Automação" e devolve os dados do pedido em JSON.

  python3 card.py card.json      (card.json = resposta do trelloReadCard action "get")

De onde vem cada dado:
  Foco ............ etiqueta Livro | Coletânea | Autor (exatamente uma)
  Origem .......... etiqueta Interno | Externo (exatamente uma)
  Veio da news .... etiqueta "News + LP" (+ campo **Cards da news:** com um link de card da news por linha;
                    cards antigos: **Card da news:** com um link só). Todas as news da lista recebem o link da LP.
  Título/nome ..... nome do card (Livro: título; Coletânea: nome da coleção; Autor: nome do autor)
  Demais .......... descrição, no formato **Campo:** valor (veja o card "📋 Modelo de pedido")
  Dados da automação: último comentário com "Dados da automação (não editar):" e uma linha em código.
"""
import json, re, sys, unicodedata

CAMPOS = {
    "autor": "Autor", "compra": "Link de compra", "outros": "Outros links de compra", "instagram": "Instagram",
    "subdominio": "Subdomínio", "pasta_global": "Pasta Global", "pasta_ases": "Pasta Ases", "modelo": "Modelo",
    "news": "Card da news", "publico": "Público", "observacoes": "Observações", "livros": "Livros",
    "foto_autor": "Foto do autor", "lp_antiga": "LP antiga",
}
# rótulos alternativos (sem acento, minúsculas) → chave
ALIASES = {"cards da news": "news"}
FOCOS = {"livro": "livro", "coletanea": "coletanea", "autor": "autor"}
MODELOS = {"editorial": "editorial", "grafico": "grafico", "infantil": "infantil"}
MARKETPLACES = ("amazon.com.br", "amazon.com", "a.co", "amzn.to", "mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com",
                "meli.la", "shopee.com.br", "shope.ee", "magazineluiza.com.br", "magalu.com", "americanas.com.br",
                "submarino.com.br", "shoptime.com.br", "estantevirtual.com.br", "umlivro.com.br")


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def host(link):
    m = re.match(r"https://([^/?#]+)", (link or "").strip().lower())
    return m.group(1).split("@")[-1].split(":")[0] if m else ""


def eh(link, dominios):
    h = host(link)
    return bool(h) and any(h == d or h.endswith("." + d) for d in dominios)


def limpar(v):
    v = re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", r"\2", v.strip()).strip("<>* ").strip()
    if re.search(r"\b(opcional|ex\.:|obrigat[oó]rio)\b", v, re.I) or v.startswith("("):
        return ""
    return v


def id_drive(link):
    m = re.search(r"/(?:d|folders)/([A-Za-z0-9_-]{10,})", link or "") or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", link or "")
    return m.group(1) if m else ""


def ler_descricao(desc):
    dados, atual = {}, None
    for linha in (desc or "").splitlines():
        m = re.match(r"\s*\*\*(.+?):\*\*\s*(.*)$", linha)
        if m:
            rotulo = sem_acento(m.group(1).split("(")[0])
            atual = ALIASES.get(rotulo) or next((k for k, n in CAMPOS.items() if sem_acento(n) == rotulo), None)
            if atual:
                dados[atual] = limpar(m.group(2))
            continue
        if atual in ("livros", "outros", "observacoes", "news") and linha.strip():
            item = limpar(re.sub(r"^\s*[-*•]\s*", "", linha))
            if item:
                dados[atual] = (dados.get(atual, "") + "\n" + item).strip()
        elif not linha.strip():
            atual = None if atual not in ("observacoes",) else atual
    return dados


def dados_automacao(card):
    for c in card.get("comments") or []:  # do mais novo para o mais antigo
        t = c.get("text") or c.get("data", {}).get("text", "")
        if "Dados da automação" in t:
            m = re.findall(r"`([^`]+)`", t.split("Dados da automação", 1)[1])
            if m:
                return m[-1]
    return ""


def ler(card):
    d = ler_descricao(card.get("desc", ""))
    etiquetas = [sem_acento(l.get("name", "")) for l in card.get("labels", [])]
    focos = [FOCOS[e] for e in etiquetas if e in FOCOS]
    origem = [e for e in etiquetas if e in ("interno", "externo")]
    falta = []
    if len(focos) != 1:
        falta.append("Uma etiqueta de foco: Livro, Coletânea ou Autor (só uma)")
    if len(origem) != 1:
        falta.append("Uma etiqueta de origem: Interno ou Externo (só uma)")
    foco = focos[0] if len(focos) == 1 else ""
    externo = origem == ["externo"]
    nome = (card.get("name") or "").strip()
    if not nome or nome.startswith("📋"):
        falta.append("Nome do card (título do livro, nome da coletânea ou do autor)")

    compra = d.get("compra", "")
    if compra and not eh(compra, MARKETPLACES):
        falta.append("Link de compra de marketplace (Amazon, Mercado Livre, Shopee, Magalu…). Site do autor, WhatsApp e Instagram não servem")
    if externo and not compra and foco == "livro":
        falta.append("Link de compra (livro externo não está no catálogo da Ases)")
    outros = []
    for l in (d.get("outros") or "").splitlines():
        url = re.search(r"https://\S+", l)
        if not url:
            continue
        u = url.group(0).rstrip(").,")
        if eh(u, MARKETPLACES):
            outros.append(u)
        else:
            falta.append(f"Outros links de compra: só marketplace (tirar {u})")

    ig = d.get("instagram", "")
    ig_status = "procurar"  # vazio: procurar no briefing
    if sem_acento(ig) in ("nao", "não", "sem", "-", "nenhum"):
        ig_status, ig = "sem", ""
    elif ig:
        m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", ig) or re.match(r"@?([A-Za-z0-9._]{2,30})$", ig)
        ig_status, ig = ("tag", m.group(1)) if m else ("invalido", ig)
        if ig_status == "invalido":
            falta.append("Instagram: só a tag (ex.: @autor), ou 'não' para LP sem Instagram")

    sub = sem_acento(d.get("subdominio", "")).replace(".bibliomarket.com.br", "")
    if sub and not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,40}[a-z0-9])?", sub):
        falta.append("Subdomínio só com letras minúsculas, números e hífen (ex.: joaquimecall)")
    modelo = MODELOS.get(sem_acento(d.get("modelo", "")).replace("á", "a"), "")
    if d.get("modelo") and not modelo:
        falta.append("Modelo: editorial, gráfico ou infantil (ou vazio para a automação escolher)")

    # links dos cards da news deste livro (sem repetir, na ordem)
    cards_news = []
    for u in re.findall(r"https://trello\.com/c/[A-Za-z0-9]+[^\s)>\]]*", d.get("news", "")):
        u = u.rstrip(".,")
        base = re.match(r"https://trello\.com/c/[A-Za-z0-9]+", u).group(0)
        if base not in [re.match(r"https://trello\.com/c/[A-Za-z0-9]+", c).group(0) for c in cards_news]:
            cards_news.append(u)

    livros = [l for l in (d.get("livros") or "").splitlines() if l.strip()]
    if foco == "coletanea" and len(livros) < 2:
        falta.append("Livros: um título por linha (a coletânea precisa de pelo menos 2)")
    if foco == "autor" and not livros:
        falta.append("Livros: os títulos do autor que entram na página, um por linha")

    return {
        "nome": nome, "foco": foco, "externo": externo, "origem": "externo" if externo else ("interno" if origem else ""),
        "veio_da_news": "news + lp" in etiquetas, "cards_news": cards_news,
        "card_news": cards_news[0] if cards_news else "",
        "autor": d.get("autor", ""), "compra": compra, "outros_links": outros,
        "instagram": ig, "instagram_status": ig_status,
        "subdominio": sub, "modelo": modelo, "publico": d.get("publico", ""),
        "livros": livros if foco != "livro" else [nome],
        "pasta_global": id_drive(d.get("pasta_global", "")), "pasta_ases": id_drive(d.get("pasta_ases", "")),
        "foto_autor": d.get("foto_autor", ""), "lp_antiga": d.get("lp_antiga", ""),
        "observacoes": d.get("observacoes", ""),
        "dados_automacao": dados_automacao(card),
        "falta": falta,
    }


if __name__ == "__main__":
    bruto = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    card = json.loads(bruto)
    if "cards" in card:
        card = card["cards"]["nodes"][0]
    print(json.dumps(ler(card), ensure_ascii=False, indent=2))
