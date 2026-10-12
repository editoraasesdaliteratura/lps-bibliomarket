<?php
// Entrega o PDF da leitura ao leitor da página, só enquanto o passe estiver válido.
declare(strict_types=1);
require __DIR__ . '/leitura-lib.php';

header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: private, no-store');

$resultado = leitura_abrir_passe((string) ($_GET['p'] ?? ''));
if ($resultado['estado'] !== 'ok') {
    http_response_code($resultado['estado'] === 'expirado' ? 410 : 403);
    exit;
}

$caminho = leitura_obter_pdf($resultado['dados']);
if ($caminho === null) {
    http_response_code(502);
    exit;
}

header('Content-Type: application/pdf');
header('Content-Disposition: inline; filename="leitura.pdf"');
header('Content-Length: ' . (string) filesize($caminho));
readfile($caminho);
