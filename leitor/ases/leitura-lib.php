<?php
/**
 * Leitura gratuita das newsletters (asesdaliteratura.com/leia/).
 *
 * Cada news traz um link com um "passe" (parâmetro p) gerado pela automação.
 * O passe é cifrado (AES-256-GCM) com a chave secreta guardada FORA do public_html,
 * em ases-private/leitura.php:
 *     <?php return ['chave' => 'COLE_A_CHAVE_AQUI'];
 * Dentro do passe vão: o arquivo, título, autor, link de compra e as datas.
 * Ninguém consegue criar um passe nem esticar o prazo sem a chave.
 *
 * O PDF nunca fica público no site. Duas origens:
 * - id do Google Drive: pdf.php busca no Drive e guarda uma cópia temporária em
 *   ases-private/leitura-cache/, apagada sozinha quando a leitura expira;
 * - "trecho:<código>": trecho já cortado que a automação enviou para leia/trechos/
 *   (pasta bloqueada para acesso direto). Também é apagado sozinho depois do prazo.
 */
declare(strict_types=1);

if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === realpath(__FILE__)) {
    http_response_code(404);
    exit;
}

const LEITURA_FUSO = 'America/Sao_Paulo';
// Trechos enviados pela automação ficam aqui por no máximo este tempo depois do fim da leitura.
const LEITURA_TRECHO_FOLGA = 2 * 86400;
// Trecho enviado sem o .json de prazo (envio interrompido) é apagado depois deste tempo.
const LEITURA_TRECHO_ORFAO = 30 * 86400;

function leitura_dir_privado(): string
{
    $env = getenv('ASES_PRIVATE_DIR');
    if (is_string($env) && trim($env) !== '') {
        return rtrim($env, DIRECTORY_SEPARATOR);
    }
    return dirname(__DIR__, 2) . '/ases-private';
}

/** Pasta dos trechos enviados pela automação: public_html/leia/trechos (com .htaccess que nega acesso direto). */
function leitura_dir_trechos(): string
{
    return dirname(__DIR__) . '/leia/trechos';
}

function leitura_config(): ?array
{
    $file = leitura_dir_privado() . '/leitura.php';
    if (!is_readable($file)) {
        return null;
    }
    $config = include $file;
    if (!is_array($config) || strlen((string) ($config['chave'] ?? '')) < 32 || str_contains((string) $config['chave'], 'COLE_')) {
        return null;
    }
    return $config;
}

function leitura_b64url_decode(string $value): ?string
{
    $raw = base64_decode(strtr($value, '-_', '+/') . str_repeat('=', (4 - strlen($value) % 4) % 4), true);
    return $raw === false ? null : $raw;
}

/**
 * Abre o passe. Retorna ['estado' => 'ok'|'expirado'|'cedo'|'invalido'|'sem-config', 'dados' => array|null].
 */
function leitura_abrir_passe(string $passe): array
{
    $config = leitura_config();
    if ($config === null) {
        return ['estado' => 'sem-config', 'dados' => null];
    }
    if ($passe === '' || strlen($passe) > 4000 || !preg_match('/^[A-Za-z0-9_-]+$/', $passe)) {
        return ['estado' => 'invalido', 'dados' => null];
    }
    $raw = leitura_b64url_decode($passe);
    if ($raw === null || strlen($raw) < 12 + 16 + 2) {
        return ['estado' => 'invalido', 'dados' => null];
    }
    $iv = substr($raw, 0, 12);
    $tag = substr($raw, -16);
    $cifrado = substr($raw, 12, -16);
    $chave = hash('sha256', (string) $config['chave'], true);
    $json = openssl_decrypt($cifrado, 'aes-256-gcm', $chave, OPENSSL_RAW_DATA, $iv, $tag);
    if ($json === false) {
        return ['estado' => 'invalido', 'dados' => null];
    }
    $dados = json_decode($json, true);
    if (!is_array($dados) || ($dados['v'] ?? null) !== 1 || !is_string($dados['f'] ?? null) || !is_int($dados['e'] ?? null)) {
        return ['estado' => 'invalido', 'dados' => null];
    }
    $agora = time();
    if ($agora > $dados['e']) {
        return ['estado' => 'expirado', 'dados' => $dados];
    }
    if (isset($dados['s']) && is_int($dados['s']) && $agora < $dados['s'] - 6 * 3600) {
        return ['estado' => 'cedo', 'dados' => $dados];
    }
    return ['estado' => 'ok', 'dados' => $dados];
}

function leitura_data_extenso(int $timestamp): string
{
    $meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
    $data = (new DateTimeImmutable('@' . $timestamp))->setTimezone(new DateTimeZone(LEITURA_FUSO));
    return $data->format('j') . ' de ' . $meses[(int) $data->format('n') - 1];
}

function leitura_link_seguro(?string $url): ?string
{
    if (!is_string($url) || $url === '') {
        return null;
    }
    $partes = parse_url($url);
    return (is_array($partes) && in_array($partes['scheme'] ?? '', ['https', 'http'], true) && !empty($partes['host'])) ? $url : null;
}

/** Apaga do cache as cópias cujo prazo já passou. Roda a cada abertura de PDF. */
function leitura_limpar_cache(string $dir): void
{
    foreach (glob($dir . '/*.json') ?: [] as $meta) {
        $info = json_decode((string) @file_get_contents($meta), true);
        if (!is_array($info) || (int) ($info['ate'] ?? 0) < time()) {
            @unlink(substr($meta, 0, -5) . '.pdf');
            @unlink($meta);
        }
    }
}

/**
 * Apaga os trechos vencidos (prazo + folga) e os enviados sem prazo há mais de 30 dias.
 * Roda a cada abertura de PDF; a automação também pode chamar limpar.php.
 */
function leitura_limpar_trechos(): int
{
    $dir = leitura_dir_trechos();
    if (!is_dir($dir)) {
        return 0;
    }
    $apagados = 0;
    $agora = time();
    foreach (glob($dir . '/*.pdf') ?: [] as $pdf) {
        $meta = substr($pdf, 0, -4) . '.json';
        $info = is_readable($meta) ? json_decode((string) @file_get_contents($meta), true) : null;
        $vencido = is_array($info)
            ? (int) ($info['ate'] ?? 0) + LEITURA_TRECHO_FOLGA < $agora
            : (int) @filemtime($pdf) + LEITURA_TRECHO_ORFAO < $agora;
        if ($vencido) {
            @unlink($pdf);
            @unlink($meta);
            $apagados++;
        }
    }
    foreach (glob($dir . '/*.json') ?: [] as $meta) {
        if (!is_file(substr($meta, 0, -5) . '.pdf') && (int) @filemtime($meta) + LEITURA_TRECHO_ORFAO < $agora) {
            @unlink($meta);
        }
    }
    return $apagados;
}

/**
 * Caminho de uma cópia local do PDF, válida até o fim da leitura. Busca no Drive na primeira vez.
 */
function leitura_obter_pdf(array $dados): ?string
{
    $config = leitura_config();
    $arquivo = (string) $dados['f'];

    // Só para a prévia local: "local:nome.pdf" lê de uma pasta de testes configurada.
    if (str_starts_with($arquivo, 'local:')) {
        $pasta = $config['pasta_teste'] ?? null;
        $nome = basename(substr($arquivo, 6));
        $caminho = is_string($pasta) ? $pasta . '/' . $nome : '';
        return ($caminho !== '' && is_readable($caminho)) ? $caminho : null;
    }

    // Trecho já cortado pela automação e enviado para leia/trechos/.
    if (str_starts_with($arquivo, 'trecho:')) {
        leitura_limpar_trechos();
        $codigo = substr($arquivo, 7);
        if (!preg_match('/^[a-f0-9]{32}$/', $codigo)) {
            return null;
        }
        $caminho = leitura_dir_trechos() . '/' . $codigo . '.pdf';
        if (!is_readable($caminho) || (string) @file_get_contents($caminho, false, null, 0, 5) !== '%PDF-') {
            leitura_log('trecho ' . $codigo . ' não encontrado no servidor');
            return null;
        }
        return $caminho;
    }

    if (!preg_match('/^[A-Za-z0-9_-]{10,100}$/', $arquivo)) {
        return null;
    }

    $dir = leitura_dir_privado() . '/leitura-cache';
    if (!is_dir($dir) && !@mkdir($dir, 0750, true)) {
        return null;
    }
    leitura_limpar_cache($dir);
    leitura_limpar_trechos();

    $pdf = $dir . '/' . $arquivo . '.pdf';
    if (is_readable($pdf) && filesize($pdf) > 0) {
        return $pdf;
    }

    $url = 'https://drive.usercontent.google.com/download?id=' . rawurlencode($arquivo) . '&export=download&confirm=t';
    $tmp = $pdf . '.baixando';
    $fh = fopen($tmp, 'wb');
    if ($fh === false) {
        return null;
    }
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_FILE => $fh,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_CONNECTTIMEOUT => 15,
        CURLOPT_TIMEOUT => 120,
        CURLOPT_USERAGENT => 'AsesLeitura/1.0',
    ]);
    $ok = curl_exec($ch);
    $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    fclose($fh);

    $inicio = (string) @file_get_contents($tmp, false, null, 0, 5);
    if ($ok !== true || $status !== 200 || $inicio !== '%PDF-') {
        @unlink($tmp);
        leitura_log('falha ao baixar ' . $arquivo . ' do Drive (HTTP ' . $status . ')');
        return null;
    }
    rename($tmp, $pdf);
    file_put_contents($dir . '/' . $arquivo . '.json', json_encode(['ate' => (int) $dados['e']]));
    return $pdf;
}

function leitura_log(string $mensagem): void
{
    $dir = leitura_dir_privado();
    if (is_dir($dir) && is_writable($dir)) {
        @file_put_contents($dir . '/leitura-erro.log', date('Y-m-d H:i:s') . ' ' . $mensagem . "\n", FILE_APPEND | LOCK_EX);
    }
}

function e(?string $texto): string
{
    return htmlspecialchars((string) $texto, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}
