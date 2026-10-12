<?php
/**
 * Capa de livro externo usada nos e-mails da Global: assessoriaglobal.com.br/leia/capa.php?c=<código>
 *
 * Na primeira vez busca a imagem pelo repasse assinado e guarda em global-private/capas/;
 * depois serve sempre a cópia local (a automação já abre este endereço logo após o envio).
 * Cópias com mais de 1 ano sem uso são apagadas sozinhas.
 */
declare(strict_types=1);
require __DIR__ . '/leitura-lib.php';

const CAPA_VALIDADE = 365 * 86400;

$codigo = (string) ($_GET['c'] ?? '');
if (!preg_match('/^[a-f0-9]{32}$/', $codigo)) {
    http_response_code(404);
    exit;
}

$dir = leitura_dir_privado() . '/capas';
if (!is_dir($dir) && !@mkdir($dir, 0750, true)) {
    http_response_code(503);
    exit;
}

$img = $dir . '/' . $codigo . '.jpg';
if (!is_readable($img)) {
    // Limpeza ocasional: só quando uma capa nova chega.
    foreach (glob($dir . '/*.jpg') ?: [] as $velha) {
        if ((int) @fileatime($velha) + CAPA_VALIDADE < time() && (int) @filemtime($velha) + CAPA_VALIDADE < time()) {
            @unlink($velha);
        }
    }
    $url = leitura_repasse_url('capa', $codigo);
    $status = $url === null ? 503 : leitura_baixar($url, $img, "\xFF\xD8\xFF");
    if ($status !== 200) {
        leitura_log('falha ao buscar capa ' . $codigo . ' (HTTP ' . $status . ')');
        http_response_code(404);
        exit;
    }
}

@touch($img, (int) filemtime($img), time());
header('Content-Type: image/jpeg');
header('Content-Length: ' . (string) filesize($img));
header('Cache-Control: public, max-age=31536000, immutable');
readfile($img);
