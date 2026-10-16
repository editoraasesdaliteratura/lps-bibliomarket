# Capivamores – pelo Brasil (Gabrielle Antunes) — notas da automação

Card LP: https://trello.com/c/gUZqKhf1 · rodada 16/10/2026 14h

## Fontes (Drive, só leitura)
- Pasta Ases: `19HiHGKCwA4uRGRB8fI2OtNarObm3b6_R` (Infantil › C › Capivamores pelo Brasil). Não há pasta do livro em Global › LIVROS (só uma capa em LIVROS INTERNOS `1RAmij7_hgagfmh7jSDzcXOQyBijjMFHb`).
- Capa frente: PREVIEW_CapaFrente_9786584870406.jpg `1mvw-ASZZOrwFdh_l05lFUVim6hm0sewy`
- Capa aberta: 9786584870406_capa.pdf `13pW6I0rElSJdOWXe881SY8yW-wLejpCb` (lombada 4 mm medida, orelhas 100 mm, 20×20 cm)
- Miolo PDF `1bzRK2Mc0ahH9GYCxnH09IYGIfBSaMPNT` (24 MB, acima do limite de download do conector: não baixado)
- Pasta LP da Ases `1O8cxfIQ9ftzNLcThz7w_0821839vfGRj`: capivamores_site.zip `1h8n1fTHeqxsEn74m-oyT0-j4ejS--JwV` (LP antiga da coleção). Dela vieram: páginas do miolo (miolo-brasil-*.webp), foto da autora, recorte do casal de capivaras, link Amazon e texto da bio.
- Catálogo: https://asesdaliteratura.com/catalogo/livros/capivamores-pelo-brasil/ (ISBN 9786584870406; link a.co/d/5c0xb1J)
- Sem briefing de marketing no Drive.

## Decisões
- Link: https://www.amazon.com.br/dp/6584870405 (o mesmo ASIN da LP antiga; o a.co do catálogo não pôde ser aberto daqui).
- Trecho = texto literal da orelha do livro (é livro de colorir, sem texto corrido).
- Vinheta: pino e bilhete do verso (sem o selo "TRAVEL", que tem texto).
- Bio: da LP antiga na pasta LP da Ases (confirmar com a autora/Renan).
- Sem crédito de ilustração (capa só traz "Idealizadora conjunta: Lorena Barros Breves Rodrigues").
- Instagram: nenhum no card nem no material → sem Instagram.

## Ajuste 16/10/2026 (pedido do Renan)
- Título mais leve: `tema.peso_titulo` 500 (Fredoka; antes 800/700). Opção nova no modelo infantil (commit 6d4a978 no main).
- Capa mais de frente: hero com `mockup-pe-22.png` (`render.py --cena pe --giro 22`; antes 34°). O `mockup-pe.png` antigo ficou no projeto.
- Autora centralizada no círculo: `autora-centrada.jpg` = recorte (155,300)-(675,820) de `autora.jpg` (zoom, rosto no centro).
- Subdomínio final: democapivamores (capivamores.bibliomarket.com.br já é a LP antiga da coleção, site separado na Hostinger; decisão do Renan em 16/10).
