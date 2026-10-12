<?php
/**
 * Repasse servidor-a-servidor para o leitor da Global (assessoriaglobal.com.br/leia/).
 *
 * A automação guarda aqui, em pastas bloqueadas para acesso direto:
 * - leia/trechos/<código>.pdf  (+ .json com {"ate": fim da leitura}) — trechos de livros externos;
 * - leia/capas/<código>.jpg    (+ .json com {"ate": ...})            — capas de externos para os e-mails.
 * Só quem tem a chave compartilhada (leia/trechos/repasse-chave.php aqui e
 * leia/repasse-chave.php na Global) consegue buscar. Leitores e e-mails nunca veem este endereço.
 *
 * GET ?tipo=trecho|capa&c=<32 hex>&t=<unix>&s=<hmac-sha256 hex de "tipo|c|t">
 */
declare(strict_types=1);
require __DIR__ . '/leitura-lib.php';

header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: private, no-store');

const REPASSE_JANELA = 600;            // assinatura vale 10 min
const REPASSE_CAPA_FOLGA = 30 * 86400; // capa fica até 30 dias depois do "ate" (a Global já guardou a sua cópia)

function repasse_negar(int $codigo): void
{
    http_response_code($codigo);
    exit;
}

/** Apaga capas vencidas (prazo + folga) e as enviadas sem prazo há mais de 90 dias. */
function repasse_limpar_capas(string $dir): void
{
    $agora = time();
    foreach (glob($dir . '/*.jpg') ?: [] as $img) {
        $meta = substr($img, 0, -4) . '.json';
        $info = is_readable($meta) ? json_decode((string) @file_get_contents($meta), true) : null;
        $vencido = is_array($info)
            ? (int) ($info['ate'] ?? 0) + REPASSE_CAPA_FOLGA < $agora
            : (int) @filemtime($img) + 90 * 86400 < $agora;
        if ($vencido) {
            @unlink($img);
            @unlink($meta);
        }
    }
}

$chaveArquivo = leitura_dir_trechos() . '/repasse-chave.php';
$config = is_readable($chaveArquivo) ? include $chaveArquivo : null;
$chave = is_array($config) ? (string) ($config['chave'] ?? '') : '';
if (strlen($chave) < 32) {
    repasse_negar(503);
}

$tipo = (string) ($_GET['tipo'] ?? '');
$codigo = (string) ($_GET['c'] ?? '');
$t = (int) ($_GET['t'] ?? 0);
$s = (string) ($_GET['s'] ?? '');

if (!in_array($tipo, ['trecho', 'capa'], true) || !preg_match('/^[a-f0-9]{32}$/', $codigo) || abs(time() - $t) > REPASSE_JANELA) {
    repasse_negar(403);
}
if (!hash_equals(hash_hmac('sha256', $tipo . '|' . $codigo . '|' . $t, $chave), $s)) {
    repasse_negar(403);
}

if ($tipo === 'trecho') {
    leitura_limpar_trechos();
    $arquivo = leitura_dir_trechos() . '/' . $codigo . '.pdf';
    $mime = 'application/pdf';
    $assinatura = '%PDF-';
} else {
    $dir = dirname(leitura_dir_trechos()) . '/capas';
    repasse_limpar_capas($dir);
    $arquivo = $dir . '/' . $codigo . '.jpg';
    $mime = 'image/jpeg';
    $assinatura = "\xFF\xD8\xFF";
}

if (!is_readable($arquivo) || (string) @file_get_contents($arquivo, false, null, 0, strlen($assinatura)) !== $assinatura) {
    repasse_negar(404);
}

$meta = substr($arquivo, 0, -strlen(pathinfo($arquivo, PATHINFO_EXTENSION)) - 1) . '.json';
$info = is_readable($meta) ? json_decode((string) @file_get_contents($meta), true) : null;
if (is_array($info) && isset($info['ate'])) {
    header('X-Ate: ' . (int) $info['ate']);
}
header('Content-Type: ' . $mime);
header('Content-Length: ' . (string) filesize($arquivo));
readfile($arquivo);
