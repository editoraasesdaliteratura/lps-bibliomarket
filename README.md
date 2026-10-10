# LPs Bibliomarket · Global Assessoria

Landing pages de livros publicadas em `*.bibliomarket.com.br` (Hostinger).

## Estrutura
- `main`: o gerador (`gerador/build.py`), os modelos (`gerador/template/`) e o conteúdo-fonte de cada LP (`gerador/exemplos/<slug>/lp.json` + imagens).
- `lp/<slug>`: um branch por LP, só com os arquivos prontos. A Hostinger clona esse branch na pasta do subdomínio do autor.

## Gerar uma LP
```
python3 gerador/build.py gerador/exemplos/<slug>/lp.json [--previa]
```
Saída em `gerador/dist/<slug>/`. `--previa` marca a página como noindex.

## Regras do domínio
- As LPs feitas no Canva vivem em `bibliomarket.com.br/<caminho>` e dependem dos registros `@` e `www` (Canva). Nunca alterar esses registros nem os TXT de verificação.
- LPs deste repositório usam subdomínios próprios; criar um subdomínio só acrescenta um registro ao DNS.
