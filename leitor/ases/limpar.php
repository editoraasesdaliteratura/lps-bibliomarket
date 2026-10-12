<?php
// Limpeza dos trechos vencidos em leia/trechos/. Pode ser chamado pela automação: /leia/limpar.php
declare(strict_types=1);
require __DIR__ . '/leitura-lib.php';
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
header('Content-Type: text/plain; charset=utf-8');
echo 'apagados ' . leitura_limpar_trechos() . "\n";
