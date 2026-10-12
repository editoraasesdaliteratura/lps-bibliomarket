# Leitor de leitura gratuita (asesdaliteratura.com/leia/)

Cópia dos arquivos PHP que estão no servidor, para histórico. O que vale é o servidor.
- `ases/leitura-lib.php`, `pdf.php`, `limpar.php` → `public_html/leia/`
- `ases/trechos.htaccess` → `public_html/leia/trechos/.htaccess` (bloqueia acesso direto)

Passe com `"f": "trecho:<32 hex>"` lê `leia/trechos/<código>.pdf` (enviado pela automação de news);
o leitor apaga o trecho 2 dias depois do fim da leitura (`<código>.json` com `ate`).
Passe com id do Drive continua como antes (cópia temporária em ases-private/leitura-cache/).
