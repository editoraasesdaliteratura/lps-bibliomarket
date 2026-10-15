---
name: "lps-bibliomarket"
description: "Monta e publica as LPs de livros e autores da Global (subdomínios do bibliomarket) a partir do Trello LP • Automação: Drive, texto, mockup 3D, prévia, publicação e link na news."
---

# LPs de livros e autores (bibliomarket) a partir do Trello

Substitui as LPs feitas no Canva pelo freelancer. O fluxo vive no quadro **LP • Automação** do Trello. A página sai **somente** do gerador no GitHub (`editoraasesdaliteratura/lps-bibliomarket`, branch `main`), vai para um branch próprio no GitHub e a Hostinger puxa por Git. Nada depende do Mac do Renan.

## Regras que nunca se quebram

1. **Drive só leitura.** Nunca editar, mover, renomear, compartilhar, copiar para dentro ou apagar nada nas pastas da Ases e da Global. A automação só baixa.
2. **Hostinger: só estas operações.** Listar (sites, subdomínios, arquivos, repositórios, DNS), `hosting_git_deploy-website-repository` (em `teste-lp/<slug>` ou `lps/<slug>`) e `hosting_domains_create-website-subdomain` para um subdomínio **novo**. Nunca criar ou recriar o site `bibliomarket.com.br` (em 25/09/2026 isso derrubou as LPs), nunca mexer em DNS, nunca tocar no ALIAS `rafaelbilhan`, nos registros do Canva e do Google, nem em pastas que a automação não criou. As LPs antigas do Canva (`bibliomarket.com.br/<nome>`) não podem parar de funcionar.
3. **Nada é apagado** (arquivo, branch, subdomínio, card) sem permissão do Renan.
4. **Publicação final só com o card em 🟢 Aprovado**, movido pelo Renan. Antes disso, só prévia em `teste-lp.bibliomarket.com.br/<slug>/` (com `noindex`).
5. **O HTML só sai do `build.py`.** Nunca escrever ou corrigir HTML/CSS à mão, nem no `dist/`, nem no servidor. Ajuste de conteúdo → `lp.json`. Ajuste de layout → template no `main`, só quando o Renan pedir (aí commit no `main` com a mudança descrita).
6. **Nada inventado.** Texto só com o que está no livro, no briefing, no catálogo, na capa ou no card. Nunca criar prêmios, números de vendas, depoimentos, citações de terceiros ou dados do autor. O trecho (citação) é cópia literal do texto do livro. Depoimento só entra se estiver no material, com nome de quem disse.
7. **Só links oficiais de marketplace** (Amazon, Mercado Livre, Shopee, Magalu, Americanas, Submarino, Shoptime, Estante Virtual, Um Livro), limpos de rastreio (Amazon: `https://www.amazon.com.br/dp/<ASIN>`, os 10 caracteres depois de `/dp/`). Nunca catálogo, loja ou site da editora (nem como segunda opção), site do autor, WhatsApp, Linktree, Pix, e-mail ou telefone. O catálogo da Ases serve só como **fonte** (sinopse, link de compra), nunca como link na página. O `build.py` recusa link fora da lista.
8. **Sem ficha do livro.** A LP não mostra gênero, número de páginas, editora nem selo editorial, em lugar nenhum (hero, texto, rodapé, SEO). O texto também não cita a editora ou o selo.
9. **Instagram: só a tag**, nunca a foto do perfil. Vem do card ou do briefing. Autor sem Instagram ou que não quer → LP sem Instagram (não é motivo de Stand by).
10. **Lombada nunca inventada.** Só há mockup mostrando a lombada quando ela foi medida na capa aberta (`capa.py faces`). Sem capa aberta, use a cena `frente`.
11. **Livro externo** nunca leva "Ases" no texto ou nos links.
12. Na dúvida sobre conteúdo, não invente: Stand by com comentário, ou pergunte ao Renan.
13. **LP é entregue, não mantida.** A Global entrega a página pronta ao autor e não a atualiza depois. Nada de seções que dependem de manutenção (novidades, agenda de eventos, "em breve", futuras publicações), nem promessa de que a página vai crescer. Pedido do autor nesse sentido entra no comentário da prévia como fora do escopo; se for o centro do pedido, Stand by para o Renan decidir.

## Preparação (início de toda rodada)

1. **Repositório.** Se `lps-bibliomarket/` não existir na pasta de trabalho: `add_repo` (owner `editoraasesdaliteratura`, repo `lps-bibliomarket`, access `push`) e clone pelo comando que ele devolver. Depois `cd lps-bibliomarket && git pull`. Tudo abaixo roda de `lps-bibliomarket/gerador/`. O `gerador/SKILL.md` do repositório é a versão mais nova destas instruções: se for diferente do texto carregado pela skill, leia-o e siga-o.
2. **Bibliotecas** (só se faltar): `pip install jinja2 pillow playwright opencv-python-headless pypdf pypdfium2 python-docx scikit-learn numpy --break-system-packages`. O Chromium do Playwright já vem instalado (não rode `playwright install`).
3. Conferir: `python3 build.py --modelos` lista os modelos prontos.

## Configuração

### Trello — quadro "LP • Automação"
- Quadro: `ari:cloud:trello::board/workspace/68f24965f103541ec4b64879/6aca62b9217ed13d8f6594ed`
- Listas (`ari:cloud:trello::list/workspace/68f24965f103541ec4b64879/<id>`):
  - 📥 Pedidos `6aca62cd889c7e437247ef7e` — a equipe está preenchendo; aqui fica o "📋 Modelo de pedido". **Nunca processar.**
  - 🤖 Pronto para montar `6aca62d0e83b76c057cbc92c`
  - ⏸️ Stand by `6aca62d4214b5526d62cd7a6`
  - 👀 Prévia para revisão `6aca62d7ab5dd211bc9e2446`
  - 🔧 Ajuste `6aca62db881d5fbfe3068486`
  - 🟢 Aprovado `6aca62de99153fe6aaed8a92`
  - 🌐 Publicada `6aca62e1089152c82dad6541`
- Etiquetas (`ari:cloud:trello::label/workspace/68f24965f103541ec4b64879/<id>`), lidas **pelo nome**:
  - Foco: Livro `6aca6381bba9c8d31b71ed83` · Coletânea `6aca639267ad5e743df5d2b8` · Autor `6aca63a6135ddebb964411d9`
  - Origem: Interno `6aca63b30dea6469040cb94c` · Externo `6aca63bf29a35d2b80e09f6c`
  - News + LP `6aca63dbb9097d43fd8889c9` (o pedido veio de um card da news)

### Trello — quadro da news ("News • Automação")
- Quadro `ari:cloud:trello::board/workspace/68f24965f103541ec4b64879/6ac8eeddf9f8cf660f0cbcb8`. Listas que podem ter pedido de LP: ⏸️ Stand by `6ac8eeff48989d9e5367c8d7`, 🤖 Pronto para montar `6ac8ef026770bcd7c41deb7d`, 📥 Entrada `6ac8eefd555f4594f5ea50dc` (só ler). Etiqueta Externo da news: `6ac933a4496b1252d72b7f6c`.
- A automação de LP só pode, no card da news: preencher o campo `**Landing page:**` e comentar. Nada mais.
- **A LP é do livro, não da news.** Um livro tem uma LP só e todas as news dele recebem o mesmo link. Valores do campo `**Landing page:**` da news: link `https://` (já tem), `criar` (pedido), vazio (usa a LP do livro se houver) ou `sem LP` (esta news nunca leva LP: nunca preencha nem vincule; também valem `sem`, `não`, `nenhuma`, `-`).

### Google Drive (conta asesdaliteratura@gmail.com, só leitura)
- **Global** — Marketing › 2.PRODUÇÃO DE CONTEÚDO › **LIVROS** `1Azkr8lx74bKRJ-mkaWYLw8o9TctRZJfA` › letra › pasta do título. Tem a pasta de **todo** livro (interno e externo): briefing de marketing, às vezes capa, miolo, foto, e um doc "LandingPage <título>" quando já existe LP antiga.
- **Ases** — `_Livros PUBLICADOS` `1u1l2VTWTsFUjFPTJTmmxuBgudSHOGDHv` › categoria › letra › título, ou pastas de produção (dono `producao.editorial.ases*`). Subpastas comuns: `PREVIEW` (`PREVIEW_<ISBN>_CapaFrente.jpg`, `PREVIEW_<ISBN>_CapaAberta.jpg`), `PDF_AJUSTADO` ou `PDF` (`<ISBN>_Capa.pdf`, `<ISBN>_miolo.pdf`, `PARK_<ISBN>_miolo.pdf`), `PSD`, `INDESIGN`, `Upload do autor`; na raiz, o texto final revisado (`*_RevFinal.docx` ou similar) e a ficha.
- **Transição:** a partir de outubro/2026 a Emilly passa a copiar todo o material para a pasta da Global. **Sempre procure primeiro na Global e só complete na Ases o que faltar.** Quando tudo estiver na Global, a Ases simplesmente deixa de ser necessária.

### Hostinger e GitHub
- Conta `u155401317`, site-pai `bibliomarket.com.br` (raiz em `.../domains/bibliomarket.com.br/public_html`; o domínio raiz aponta para o Canva, a Hostinger só serve os subdomínios).
- Repositório para a Hostinger: `git@github.com:editoraasesdaliteratura/lps-bibliomarket.git` (chave de deploy só leitura já cadastrada).
- **Prévia:** branch `lp/previa-<slug>` → pasta `teste-lp/<slug>` → `https://teste-lp.bibliomarket.com.br/<slug>/`.
- **Final:** branch `lp/<slug>` → pasta `lps/<slug>` → subdomínio `https://<sub>.bibliomarket.com.br/`.
- **Projeto** (lp.json + imagens, para ajustes futuros): branch `projeto/<slug>` (`ferramentas/projeto.py`).
- Cada envio do `publicar.py` é um commit novo em cima do anterior (a Hostinger só avança com `pull`). Nunca reescreva o histórico de um branch `lp/*` (nada de force push à mão). Se um deploy falhar com "divergent branches", leia o commit que o servidor tem (`hosting_files_website-content` em `<pasta>/.git/refs/heads/<branch>`) e publique de novo com `publicar.py ... --base <esse commit>`.

## O card de pedido ("📋 Modelo de pedido")
| Dado | Onde |
|---|---|
| Título do livro / nome da coletânea / nome do autor | nome do card |
| Foco | etiqueta **Livro**, **Coletânea** ou **Autor** |
| Interno ou externo | etiqueta **Interno** ou **Externo** |
| Link de compra | `**Link de compra:**` (externo: obrigatório; interno: vazio = do catálogo da Ases) |
| Outros links | `**Outros links de compra:**` um por linha (opcional) |
| Instagram | `**Instagram:**` @tag; vazio = procurar no briefing; `não` = sem Instagram |
| Subdomínio | `**Subdomínio:**` (opcional; vazio = a automação propõe na prévia) |
| Pastas | `**Pasta Global:**` / `**Pasta Ases:**` links (opcionais; vazio = a automação procura) |
| Modelo | `**Modelo:**` editorial, gráfico ou infantil (opcional; vazio = a automação escolhe) |
| Livros | `**Livros:**` um título por linha (só Coletânea e Autor) |
| Cards da news | `**Cards da news:**` um link de card da news por linha (com a etiqueta News + LP). Cards antigos: `**Card da news:**` com um link só (o `card.py` lê os dois e devolve `cards_news`) |
| Observações | `**Observações:**` pedidos do autor, o que destacar ou evitar |

O que a equipe escreveu no card vale mais que o automático. `ferramentas/card.py card.json` lê tudo isso e devolve `falta`.

## Comentários no card
Para a Emilly e o Renan: título em negrito com emoji, bullets curtos, links `[texto](url)` (nunca crus) e **Próximo passo** claro. Os dados que a automação relê ficam no fim, depois de `---`, em "Dados da automação (não editar):" seguido de uma linha em código. É por esse bloco que a automação reconhece os próprios comentários (o conector comenta com a conta do Renan).

Stand by (falta material ou decisão):
```
**⏸️ Falta material para montar a LP**

- <item, em linguagem simples, dizendo onde colocar>
- <outro item>

**Próximo passo:** complete e mova de volta para 🤖 Pronto para montar.

---
Dados da automação (não editar):
`stand by`
```
Para modelo que ainda não existe (Coletânea e Autor, enquanto não estiverem em `build.py --modelos`), o mesmo formato com o bloco `stand by · modelo <nome>`: a cada rodada, se o modelo já existir, a automação move de volta para 🤖 Pronto para montar sozinha e comenta `**▶️ Modelo disponível.** Retomando a montagem.`

## Rodada completa ("roda as LPs")

Monte uma lista de tarefas e processe um card por vez.

### 0. Pedidos que vêm da news
Leia os cards das listas da news citadas acima. Para cada card com `**Landing page:**` igual a uma destas palavras (a mesma lista da news, sem acento e sem diferenciar maiúsculas): `criar`, `pedir`, `fazer`, `solicitar`, `sim`, `nova`, `criar lp`, `pedir lp`, procure o card do livro no quadro de LP (`trelloSearch` pelo título, só cards com etiqueta **Livro** e nome igual ao título, ignorando maiúsculas, acentos e pontuação). A skill da news faz o mesmo quando roda antes: **nunca duplique** o card de LP.
- **Já existe e está em 🌐 Publicada** → no card da news, preencha `**Landing page:** <link publicado>` (do bloco "Dados da automação" do card de LP) e comente `**🌐 Landing page publicada:** [abrir](<link>)`. Vincule a news ao card de LP (abaixo).
- **Já existe em outra lista** → vincule a news ao card de LP e comente no card da news: `**🌐 LP em produção.** Este livro já tem LP na automação de LP; o link entra aqui quando for publicada.`
- **Não existe** → crie o card em 🤖 Pronto para montar: nome = título do livro; etiquetas **Livro**, **News + LP** e **Externo** se o card da news tiver a etiqueta Externo, senão **Interno**; descrição no formato do modelo, com `**Cards da news:**` e o link do card da news na linha de baixo (`- <link>`) e, se houver, o `**Link de compra:**` da news. Comente no card da news: `**🌐 LP pedida.** A automação de LP vai montar e colocar o link aqui quando for publicada.`

**Vincular a news ao card de LP:** no card de LP, o campo `**Cards da news:**` lista um card da news por linha (`- <link>`). Card antigo com `**Card da news:** <link>` → troque por `**Cards da news:**` com esse link na primeira linha. Acrescente o link desta news se ainda não estiver na lista (`trelloWriteCard` `update`, campo `desc`, mexendo só nesse campo) e ponha a etiqueta **News + LP** se o card não tiver.

### 1. Ler o quadro de LP
`trelloReadCard` `list_by_list` em ⏸️ Stand by, 🤖 Pronto para montar, 🔧 Ajuste e 🟢 Aprovado. Em Stand by, só mexa nos cards com `stand by · modelo <nome>` (veja acima).

### 2. Cards em 🤖 Pronto para montar
1. **Ler o card.** Salve a resposta do `trelloReadCard` (`get`) em `card.json` → `python3 ferramentas/card.py card.json`. `falta` não vazio → Stand by (comentário acima) e próximo card.
2. **Modelo existe?** Foco Coletânea/Autor sem modelo em `build.py --modelos` → Stand by `stand by · modelo <coletanea|autor>`. Livro infantil (até ~10 anos, ilustrado, qualquer selo) usa o modelo `infantil`.
3. **Achar as pastas** (seção "Drive" acima): campo do card; senão `search_files` com `title = '<título>' and mimeType = 'application/vnd.google-apps.folder'` (se não achar, `title contains '<palavra marcante>'`). Global = pasta cuja mãe é uma letra dentro de LIVROS (`get_file_metadata` da mãe tem `parentId` `1Azkr8lx74bKRJ-mkaWYLw8o9TctRZJfA`). Ases = pasta com `PREVIEW`/`PDF_AJUSTADO`/`PDF`/`*RevFinal*` dentro. Liste os arquivos (`parentId = '<pasta>'`) e as subpastas relevantes.
4. **Inventário.** Monte a tabela do que existe (com id e tamanho):
   | Material | Onde procurar, em ordem |
   |---|---|
   | Capa da frente | arquivo com "CapaFrente" no nome (`PREVIEW_<ISBN>_CapaFrente.jpg`, `CapaFrente_<título>.jpg`); arquivo com "capa"/"frente" na Global; `og:image` do catálogo (interno) |
   | Capa aberta (lombada) | `<ISBN>_Capa.pdf` em `PDF_AJUSTADO`/`PDF` (melhor: medidas exatas); arquivo com "CapaAberta" no nome; capa aberta enviada pelo autor (PDF ou imagem) |
   | Miolo PDF (proporção exata) | `<ISBN>_miolo.pdf` ou `PARK_<ISBN>_miolo.pdf`; miolo do externo na Global |
   | Texto do livro | `*RevFinal*.docx` / `.doc` (texto final revisado, o preferido); senão o miolo PDF |
   | Briefing | arquivo com "briefing" na pasta da Global (sempre procure) |
   | Sinopse, autor, ISBN, compra | catálogo da Ases (interno): `https://asesdaliteratura.com/catalogo/?s=<título>` → página do livro (WebFetch ou navegador) |
   | Bio do autor | briefing; orelha/contracapa (na capa aberta); catálogo; texto do livro (sobre o autor) |
   | Foto do autor | arquivo de foto na Global/Ases/"Upload do autor"; orelha da capa aberta (recorte) |
   | Instagram | card; briefing |
   | LP antiga | doc "LandingPage <título>" na Global (só para citar no comentário; não bloqueia) |
5. **Mínimo para seguir** (faltou algum → Stand by dizendo exatamente o que e onde colocar):
   - capa da frente em imagem ou PDF;
   - link de compra de marketplace (externo: no card; interno: card ou catálogo);
   - texto do livro **ou** sinopse completa (catálogo, briefing ou card), suficiente para escrever sinopse e 3 diferenciais sem inventar;
   - bio do autor (pode ser curta). Foto **não** é obrigatória.
   Sem capa aberta não é Stand by: a LP sai com a cena `frente` (sem lombada) e o comentário da prévia diz que a capa aberta melhora o mockup.
6. **Baixar.** `download_file_content` de cada arquivo. Quando o resultado vier salvo em arquivo (`.../tool-results/*.txt`), converta: `python3 ferramentas/drive.py <arquivo.txt> projeto/<slug>/fonte/`. Arquivo pequeno que voltar inline: para texto, prefira `read_file_content`; para imagem, peça de novo ou use outra fonte. Briefing e docs do Google: `read_file_content`. Nunca baixe vídeos nem PSD/INDESIGN.
7. **Texto do livro.** `python3 ferramentas/texto.py fonte/<livro>.docx --saida livro.md --resumo` (mapa de capítulos). Leia o começo (apresentação, prefácio, 1º capítulo) e trechos ao longo do livro; não leia o livro inteiro de uma vez. Use para tom, temas, personagens e a citação literal.
8. **Capa → faces e mockups** (pasta do projeto):
   - `python3 ferramentas/capa.py faces --saida faces --frente fonte/<frente> [--pdf-capa fonte/<Capa.pdf> | --aberta fonte/<CapaAberta.jpg>] [--pdf-miolo fonte/<miolo.pdf>] [--paginas N]`
   - **Olhe `faces/conferencia.jpg`**: as linhas rosa marcam frente e contracapa; azul, as bordas. Confira `confianca` (≥ 0,9 é ótimo), `mm` (frente, altura, lombada) e `avisos`. Lombada errada → não use a cena `pe`.
   - Mockups (PNG transparente): `python3 mockup/render.py faces mockup-pe.png --cena pe` (com lombada) ou `--cena frente` (sem lombada); `--cena par` mostra frente e contracapa (bom para a seção final ou diferenciais quando a contracapa é bonita). Olhe cada PNG antes de usar.
   - Paleta: `python3 ferramentas/capa.py paleta faces/frente.jpg --amostra paleta.png` (olhe a amostra).
   - Elementos gráficos da capa (ornamento, vinheta, ilustração, personagens, foto da orelha): renderize a capa aberta em alta (`capa.py pdf <Capa.pdf> fonte/aberta.jpg --altura 3000`), olhe, escolha as coordenadas e `python3 ferramentas/capa.py recortar fonte/aberta.jpg x0 y0 x1 y1 saida.png`. Opções: `--tirar-claro [--cor '#hex']` (ornamento impresso sobre papel/fundo claro → PNG transparente, traço numa cor só), `--tirar-fundo '#hex' --tol 60` (fundo de cor chapada), `--circulo`, `--rel` (coordenadas de 0 a 1). Confira cada recorte olhando, sobre fundo claro e escuro. Recortes nunca levam texto, logo de selo/editora ou código de barras da capa.
9. **Escrever o `lp.json`** (seção "Conteúdo" e "Direção visual" abaixo; exemplos em `exemplos/`). Slug = título em minúsculas sem acento, com hífens, curto (ex.: `joaquim-e-call`). Subdomínio: veja "Nome do subdomínio" abaixo; confira que não existe (`hosting_domains_list-website-subdomains`).
10. **Gerar e conferir:**
    - `python3 build.py projeto/<slug>/lp.json --previa --url https://teste-lp.bibliomarket.com.br/<slug>/ --saida dist`
    - `AVISO` de contraste → ajuste as cores no `lp.json` e gere de novo (não ignore contraste abaixo de 4,5 em texto corrido).
    - `python3 ferramentas/verificar.py dist/<slug>` → `erros` tem que estar vazio. **Olhe todos os prints** (desktop e celular) com Read e confira: hierarquia, alinhamento, cortes, sobreposição, texto estourando, imagem pixelada, contraste, ritmo entre seções, botão visível na primeira dobra do celular. Corrija no `lp.json` (ou nas imagens) e gere de novo até estar no padrão que o Renan aprovaria.
11. **Salvar o projeto:** escreva `projeto/<slug>/notas.md` (fontes usadas com ids do Drive, decisões, pendências) e `python3 ferramentas/projeto.py salvar projeto/<slug> <slug>`.
12. **Prévia no ar:**
    - `python3 ferramentas/publicar.py dist/<slug> --branch lp/previa-<slug>`
    - `hosting_git_deploy-website-repository`: username `u155401317`, domain `bibliomarket.com.br`, repository_url `git@github.com:editoraasesdaliteratura/lps-bibliomarket.git`, branch `lp/previa-<slug>`, directory `teste-lp/<slug>`. `is_success` false → leia o log; pasta já ocupada por outra coisa → Stand by e avise o Renan (não apague).
    - Confira no ar com WebFetch (a rede da sessão normalmente não alcança o bibliomarket): título, h1, `noindex`, link do botão de compra e lista de imagens batem com o gerado.
13. **Comentar e mover para 👀 Prévia para revisão:**
    ```
    **👀 Prévia da LP pronta**

    - **Ver:** [Abrir prévia](https://teste-lp.bibliomarket.com.br/<slug>/) (não aparece no Google)
    - **Modelo:** <editorial | gráfico | infantil> · **Mockup:** <com lombada medida (X mm) | só frente: falta a capa aberta>
    - **Endereço final proposto:** <sub>.bibliomarket.com.br (para trocar, edite o campo Subdomínio antes de aprovar)
    - **Compra:** [<marketplace>](<link>) <+ outros marketplaces>
    - **Instagram:** @<tag> | sem Instagram (<motivo>)
    - **Fontes:** briefing [<nome>](<link>) · texto [<arquivo>](<link>) · capa [<arquivo>](<link>)
    - **Atenção:** <pendências: foto do autor ausente, bio curta, LP antiga existente em <link>, dado a confirmar>

    **Próximo passo:** para publicar, mova para 🟢 Aprovado. Para ajustar, comente o que mudar e mova para 🔧 Ajuste.

    ---
    Dados da automação (não editar):
    `prévia <slug> · sub <sub> · modelo <modelo> · projeto projeto/<slug>`
    ```

### 3. Cards em 🔧 Ajuste
1. Leia os comentários posteriores ao último comentário da automação e a descrição atual.
2. `python3 ferramentas/projeto.py baixar <slug> projeto/<slug>` (o slug está no bloco "Dados da automação").
3. Aplique o pedido no `lp.json` (texto, ordem, cores, fonte, imagem, cena do mockup). Pedido que exige mudar o layout do modelo → comente explicando que precisa de mudança no template, sugira a solução e deixe em Ajuste para o Renan decidir. Material novo citado (foto, capa aberta) → baixe e refaça a etapa correspondente.
4. Refaça os passos 10 a 13 (mesmo slug e mesma pasta de prévia: o deploy só puxa a nova versão). No comentário, liste em uma linha o que mudou.
5. Card que já estava publicado e voltou para Ajuste: a prévia é atualizada; o site final só muda depois de nova aprovação.

### 4. Cards em 🟢 Aprovado
1. Pegue `slug` e `sub` do bloco "Dados da automação" do último comentário da automação; se o campo Subdomínio do card mudou depois, ele vale. Baixe o projeto (`projeto.py baixar`).
2. **Subdomínio livre?** `hosting_domains_list-website-subdomains` (username `u155401317`, domain `bibliomarket.com.br`) e `hosting_websites_list`: se `<sub>.bibliomarket.com.br` já existe e **não** é desta LP (pasta diferente de `lps/<slug>`), pare: Stand by pedindo outro subdomínio. Nunca use `teste-lp`, `www`, `rafaelbilhan` nem nomes de LPs antigas.
3. **Gerar a versão final:** `python3 build.py projeto/<slug>/lp.json --url https://<sub>.bibliomarket.com.br/ --saida dist` (sem `--previa`: entra canonical, robots liberado) → `verificar.py` sem erros.
4. `python3 ferramentas/publicar.py dist/<slug> --branch lp/<slug>`
5. **Primeira publicação** (subdomínio ainda não existe):
   1. `hosting_git_deploy-website-repository` com branch `lp/<slug>` e directory `lps/<slug>` (pasta nova e vazia: o clone funciona).
   2. `hosting_domains_create-website-subdomain`: username `u155401317`, domain `bibliomarket.com.br`, subdomain `<sub>`, directory `lps/<slug>`.
   3. Confira `hosting_domains_list-website-subdomains`: o novo subdomínio aponta para `.../public_html/lps/<slug>`.
   **Republicação** (já existe e aponta para `lps/<slug>`): só o deploy (ele puxa a versão nova).
6. **Conferir no ar** `https://<sub>.bibliomarket.com.br/` com WebFetch (título, canonical, sem `noindex`, botão de compra, imagens). O certificado HTTPS de subdomínio novo pode levar alguns minutos (o WebFetch responde `ROBOTS_DISALLOWED` enquanto isso): espere uns 5 minutos e confira de novo antes de comentar; se continuar, comente avisando.
7. Comente e mova para 🌐 Publicada:
   ```
   **🌐 LP publicada:** [<sub>.bibliomarket.com.br](https://<sub>.bibliomarket.com.br/)

   - Prévia continua em teste-lp para comparação.
   - <News atualizadas com o link: N cards (<títulos/datas>). | Nenhuma news deste livro.>

   ---
   Dados da automação (não editar):
   `publicada https://<sub>.bibliomarket.com.br/ · slug <slug> · branch lp/<slug>`
   ```
8. **News (todas as do livro):** o link vai para **todas** as news deste livro que ainda podem recebê-lo, não só a que pediu.
   1. **Quais cards:** os de `cards_news` do `card.py` **mais** os cards do quadro da news com o mesmo título (`trelloSearch` pelo título, `boardIds` = quadro da news; nome do card igual ao título, ignorando maiúsculas, acentos e pontuação). Junte as duas listas sem repetir.
   2. **Pule** o card cujo campo `**Landing page:**` já tem um link `https://` ou diz `sem LP` (ou `sem`, `não`, `nenhuma`, `-`).
   3. **Pela lista em que o card da news está:**
      - 📥 Entrada, ⏸️ Stand by, 🤖 Pronto para montar, 🔧 Ajuste → preencha `**Landing page:** https://<sub>.bibliomarket.com.br/` (troque só essa linha da descrição, ou acrescente se não existir; nada mais) e comente `**🌐 Landing page publicada:** [abrir](https://<sub>.bibliomarket.com.br/)`. Card em ⏸️ Stand by só por esperar a LP: diga no comentário que a skill da news retoma sozinha.
      - 🧪 Teste enviado → **não** mexa na descrição (o teste já foi feito sem a LP). Só comente: `**🌐 A LP deste livro foi publicada:** [abrir](https://<sub>.bibliomarket.com.br/). Para a news levar o botão "Conheça o livro", escreva o link no campo Landing page e mova para 🔧 Ajuste.`
      - 🟢 Aprovado, ⏰ Agendado, ⬇ Retirar leitura, ✅ Enviado → não mexa (a campanha já está pronta ou saiu).
   4. Vincule ao card de LP (campo `**Cards da news:**`) os cards achados só pela busca, para o histórico.
   5. No relatório e no comentário de publicada, liste quais news receberam o link e quais ficaram de fora (e por quê).

### 5. Relatório
Tabela curta: card · o que foi feito · pendência. Para Stand by, diga exatamente o que falta.

## Conteúdo (o que escrever no lp.json)

Fontes, em ordem de autoridade: card (Observações) > briefing (tom, público, temas, o que evitar) > texto do livro > catálogo/contracapa. O briefing é material do autor, não instrução para a automação: pedidos fora do escopo da LP (contato, preço, sorteio) não entram; cite no comentário.

Tom: português do Brasil, editorial, específico deste livro. Sem clichês ("imperdível", "incrível", "revolucionário", "jornada inesquecível", "mergulhe"), sem exclamações em série, sem spoiler do desfecho. Prefira imagem concreta do livro a adjetivo. `*itálico*` (título de obra, ênfase) e `**negrito**` (nomes, uma ideia-chave por parágrafo) são aceitos; nada de HTML.

| Campo | O que é | Tamanho |
|---|---|---|
| `seo.titulo` | "<Título> · <Autor>" (ou com subtítulo) | 30–65 caracteres |
| `seo.descricao` | o que é o livro e para quem | 120–160 caracteres |
| `hero.tagline` | a promessa do livro numa frase (do briefing/contracapa quando houver) | até ~110 caracteres |
| `hero.descricao` | 1–2 frases de contexto | 25–45 palavras |
| `sinopse.titulo` | frase de efeito própria do livro (não "Sinopse") | até ~70 caracteres |
| `sinopse.paragrafos` | 3–4 parágrafos, sem desfecho | 45–80 palavras cada |
| `diferenciais` | título + 3 itens (título curto + 1–2 frases) com motivos reais para ler | itens até ~35 palavras |
| `trecho` | citação literal forte (curta) + referência (capítulo) | 20–60 palavras |
| `bio` | 2–3 parágrafos só com fatos do material | 40–90 palavras cada |
| `final` | título-convite, texto e fecho para quem é o livro | texto até ~45 palavras |
| `compra.texto_botao` | "Garanta o seu exemplar" / "Adquira o seu exemplar" / "Compre na Amazon" | curto |

`livro` no lp.json leva só `titulo` (e `subtitulo`/`titulo_completo` se houver), `autor` e `isbn` (o ISBN vai só nos metadados para o Google, não aparece). Gênero, páginas, editora e selo não entram (regra 8).

## Nome do subdomínio
O campo Subdomínio do card sempre manda. Sem ele, a automação propõe na prévia, sempre sem acentos, sem hífens e em minúsculas, fácil de digitar e de achar:
| Foco | Regra | Exemplos |
|---|---|---|
| Livro | título simplificado: o núcleo que o leitor lembraria, sem artigos, preposições e subtítulo; até ~20 caracteres | "Joaquim & Call: o mundo submerso" → `joaquimecall` · "A História Divina do Pão de Queijo" → `paodequeijo` · "Eu faria tudo outra vez" → `eufariatudooutravez` |
| Autor | nome pelo qual o autor é conhecido (o da capa) | Jil Delanis → `jildelanis` |
| Coletânea | nome da coleção quando ela tem nome próprio (é o que se divulga e deixa o nome do autor livre para uma futura LP de autor); sem nome próprio, o nome do autor | Coleção Lola → `colecaolola` |

Já existe (subdomínio ou LP antiga do Canva com o mesmo nome)? Acrescente uma palavra curta que diferencie (`livro`, o sobrenome do autor), nunca número.

## Direção visual

O padrão é o do Renan: clean, sofisticado, com personalidade, sem cara de template. A LP tem que parecer feita para **este** livro: cores, fontes e elementos gráficos saem da capa.

**Escolha do modelo** (`modelo` no lp.json; campo Modelo do card manda):
| Livro | Modelo |
|---|---|
| Adulto: romance, memórias, biografia, não ficção, religioso, poesia, autoajuda; capas fotográficas, tipográficas ou sóbrias | `livro-unico` (editorial) |
| Juvenil/infantojuvenil, fantasia, aventura, HQ, ação; capas ilustradas, saturadas, com personagens | `livro-grafico` |
| Infantil (até ~10 anos; livro ilustrado, de qualquer selo) | `infantil` |

**Cores:** parta da `paleta`. Editorial: `claro` (fundo principal, quase branco puxado para o tom da capa), `medio` (hero/final, um tom da capa suavizado), `escuro` (sinopse/bio, o tom mais profundo da capa), `destaque` (título e botão; a cor mais marcante, escurecida se precisar de contraste), `rodape`. Gráfico: `noite`/`noite_2` (fundo escuro da capa), `azul` (seção de cor), `lava`/`lava_2` (acento luminoso), `vermelho` (contorno/alerta), `portal` (brilho), `papel`/`tinta`. Contraste mínimo 4,5 em texto corrido: o `build.py` avisa.

**Fontes:** editorial `fonte_titulo` entre DM Serif Display, Playfair Display, Fraunces, Cormorant Garamond, Instrument Serif (literário), Bricolage Grotesque, Space Grotesk (contemporâneo), Baloo 2 (leve/infantojuvenil); escolha a que conversa com a tipografia da capa. Gráfico: `fonte_titulo` Anton (impacto), Bricolage Grotesque, Baloo 2, DM Serif Display, Fraunces; `fonte_texto` Montserrat ou DM Sans.

**Imagens (sem fotos de banco, sem cenas):**
- Hero: `mockup-pe.png` (com lombada) ou `mockup-frente.png`.
- Diferenciais (editorial, opcional): `mockup-par.png` (frente + contracapa), um detalhe da capa ou nada (a lista ocupa a largura).
- Final: outra cena do mockup ou arte da capa recortada (personagem, orelha) em PNG transparente.
- `tema.ornamento` (editorial, opcional): **peça de canto** recortada da capa em PNG transparente, orientada como canto superior esquerdo (o modelo espelha para o canto do hero, do trecho e do final). `tema.ornamento_opacidade` 0,3–0,9 (0,5–0,6 costuma bastar).
- `tema.divisor` (editorial, opcional): vinheta horizontal da capa ou do miolo (PNG transparente); o modelo recolore sozinho (cor de destaque nas seções claras, texto claro nas escuras) e põe acima do título da sinopse e da citação (com vinheta, a aspa da citação some).
- `tema.textura` (editorial, opcional): padrão repetível tirado do miolo (máscara em tons de cinza, branco = traço, recortada exatamente num período para emendar sem costura). O modelo tinge com `tema.textura_cor` (nome de cor da paleta, padrão `escuro`) e `tema.textura_opacidade` (0,04–0,08) e aplica no fundo do hero e do trecho, com `tema.textura_largura` px por bloco (padrão 260). Bom para LP sem foto/Instagram que fica "seca" no início.
- `galeria` (editorial, opcional): seção "Das páginas do livro" logo depois da sinopse, com 2 a 4 ilustrações do miolo: `{"titulo", "intro", "itens": [{"imagem", "legenda", "alt"}]}`. Imagens em retrato (página inteira serve; o modelo corta em 3:4). Legenda curta e conferida no texto do livro (o que a cena mostra), crédito da ilustradora no `intro`. Evite cenas de violência, sangue ou apelo sexual e não entregue o final.
- **Ilustrações do miolo:** quando houver (pasta de ilustrações/lâminas no Drive ou anexada), elas valem mais que recortes da capa: galeria, imagem dos diferenciais, vinheta, textura e até a foto do autor (página "sobre o autor"). TIFF em CMYK: converta com o perfil ICC embutido (`ImageCms.profileToProfile`, saída sRGB) antes de recortar, senão as cores saem lavadas ou esverdeadas.
- `diferenciais.imagem` + `"proporcao": "natural"`: detalhe ilustrado da capa (cena, objeto) mostrado inteiro, sem corte.
- Ornamento e vinheta só se o elemento for limpo e reconhecível; recorte mal feito fica pior que nada.
- Gráfico: `tema.motivos` entre `rachaduras` (fissuras luminosas), `retícula` (pontos de HQ), `portal` (brilho circular), `quadrinho` (balão da pergunta). Use só os que a capa justifica. `personagens` só quando a capa mostra os personagens e o texto os apresenta (retratos recortados da capa, 1 por card).
- Foto do autor: só se veio no material; recorte da orelha vale. Sem foto, a bio fica só em texto (os modelos já tratam).

### Modelo infantil (`"modelo": "infantil"`)
Claro, arredondado e com cara de aquarela: hero com mockup sobre mancha de aquarela e corações, história, **páginas do livro** (galeria das ilustrações do miolo), motivos para ler junto (cards com ícone), trecho com ilustração, bio com retrato redondo e chamada final. Projeto de referência: branch `projeto/o-dia-em-que-levei-um-cavalo-pra-casa` (`projeto.py baixar`).
- **Cores** (`tema.cores`): `papel` (fundo claro principal), `creme` (hero, motivos, final), `sol` (cor alegre da capa: galeria, mancha, ícones), `sol_2` (um tom acima do `sol`, só para a estampa), `tinta` (texto), `destaque` (títulos), `botao`/`botao_texto` (opcional; padrão = destaque e branco), `profundo` (seção da autora; tom escuro da capa), `texto_claro`, `acento` (opcional). O `build.py` avisa contraste baixo.
- **Fontes:** `fonte_titulo` Grandstander (traço de marcador, padrão), Baloo 2, Fredoka ou Sniglet; `fonte_texto` Nunito (padrão) ou Quicksand. Escolha a que lembra o letreiro da capa.
- **`tema.estampa`:** `coracoes`, `estrelas`, `bolinhas` ou `nenhuma`, desenhada na cor `sol_2` no fundo da galeria. Use a que a capa justifica (ex.: orelhas com corações).
- **`tema.divisor`:** vinheta da capa (PNG transparente) acima do título da história, em cor original.
- **`galeria`** (opcional, recomendada): `titulo`, `intro`, 2–4 `itens` com `imagem` (ilustração do miolo em JPG: pasta de ilustrações finais ou página do miolo), `legenda` curta e `alt`. **Nada de ilustração do desfecho** (spoiler). Ilustrações do miolo são arte do livro, não "foto": podem entrar.
- **`sinopse.imagem`** (opcional): recorte PNG ao lado do texto; sem ela a história fica centralizada.
- **`diferenciais.itens[].icone`:** `coracao`, `estrela`, `livro`, `folha`, `casa`, `sol`, `balao`, `patinha`, `lapis`, `lupa`.
- **`trecho.imagem`** (opcional): ilustração em JPG (ex.: arte da orelha), mostrada como cartão.
- **`livro.ilustrador`:** crédito "Ilustrações de …" no hero (só se estiver na capa/ficha).
- **`compra.texto_topo`:** botão curto do topo ("Comprar"), que no celular garante compra na primeira dobra quando não há Instagram.
- **Bio:** `bio.foto` é recortada em quadrado e mostrada em círculo; `bio.rotulo` padrão "Sobre a autora" (troque para "Sobre o autor").
- Recortes de personagens da capa (PNG transparente) ficam bons na chamada final; mockup no hero.

## Limites conhecidos
- O conector do Trello não cria nem renomeia etiquetas e não adiciona membros.
- A rede da sessão não alcança o Google Fonts nem o bibliomarket: o `verificar.py` usa as mesmas fontes vindas do npm (@fontsource) para os prints ficarem fiéis, e a conferência no ar é por WebFetch.
- Os modelos de Coletânea e Autor estão em construção (Stand by `stand by · modelo …` até existirem).
- Os branches `lp/previa-*` e `projeto/*` ficam no GitHub; limpeza só com permissão do Renan.