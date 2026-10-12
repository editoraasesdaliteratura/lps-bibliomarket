<?php
/**
 * Leitura gratuita das newsletters da Global (assessoriaglobal.com.br/leia/), para livros externos.
 * Mesmo motor do leitor da Ases (asesdaliteratura.com/leia/), com chave própria.
 *
 * Cada news traz um link com um "passe" (parâmetro p) gerado pela automação.
 * O passe é cifrado (AES-256-GCM) com a chave secreta guardada FORA do public_html,
 * em global-private/leitura.php (ao lado do public_html):
 *     <?php return ['chave' => 'COLE_A_CHAVE_AQUI'];
 * Dentro do passe vão: o arquivo, título, autor, link de compra e as datas.
 * Ninguém consegue criar um passe nem esticar o prazo sem a chave.
 *
 * O PDF nunca fica público no site. Duas origens:
 * - id do Google Drive: pdf.php busca no Drive;
 * - "trecho:<código>": trecho já cortado pela automação, buscado de servidor para servidor
 *   (repasse assinado com leia/repasse-chave.php). O endereço de origem nunca aparece para o leitor.
 * Nos dois casos a cópia fica em global-private/leitura-cache/ e é apagada sozinha quando a leitura expira.
 */
declare(strict_types=1);

if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === realpath(__FILE__)) {
    http_response_code(404);
    exit;
}

const LEITURA_FUSO = 'America/Sao_Paulo';
const LEITURA_REPASSE_URL = 'https://asesdaliteratura.com/leia/repasse.php';

function leitura_dir_privado(): string
{
    $env = getenv('GLOBAL_PRIVATE_DIR');
    if (is_string($env) && trim($env) !== '') {
        return rtrim($env, DIRECTORY_SEPARATOR);
    }
    return dirname(__DIR__, 2) . '/global-private';
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
 * Baixa $url para $destino (via arquivo temporário) e confere a assinatura do início do arquivo.
 * Devolve o status HTTP (0 em falha de conexão); o destino só é criado se tudo estiver certo.
 */
function leitura_baixar(string $url, string $destino, string $assinatura): int
{
    $tmp = $destino . '.baixando';
    $fh = fopen($tmp, 'wb');
    if ($fh === false) {
        return 0;
    }
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_FILE => $fh,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_CONNECTTIMEOUT => 15,
        CURLOPT_TIMEOUT => 120,
        CURLOPT_USERAGENT => 'GlobalLeitura/1.0',
    ]);
    $ok = curl_exec($ch);
    $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    fclose($fh);

    $inicio = (string) @file_get_contents($tmp, false, null, 0, strlen($assinatura));
    if ($ok !== true || $status !== 200 || $inicio !== $assinatura) {
        @unlink($tmp);
        return $status === 200 ? 422 : $status;
    }
    rename($tmp, $destino);
    return 200;
}

/** Endereço assinado do repasse (trecho ou capa guardados pela automação). Null se a chave não estiver instalada. */
function leitura_repasse_url(string $tipo, string $codigo): ?string
{
    $arquivo = __DIR__ . '/repasse-chave.php';
    $config = is_readable($arquivo) ? include $arquivo : null;
    $chave = is_array($config) ? (string) ($config['chave'] ?? '') : '';
    if (strlen($chave) < 32) {
        leitura_log('repasse-chave.php ausente ou inválida');
        return null;
    }
    $t = time();
    return LEITURA_REPASSE_URL . '?' . http_build_query([
        'tipo' => $tipo,
        'c' => $codigo,
        't' => $t,
        's' => hash_hmac('sha256', $tipo . '|' . $codigo . '|' . $t, $chave),
    ]);
}

/**
 * Caminho de uma cópia local do PDF, válida até o fim da leitura. Busca na origem na primeira vez.
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

    $trecho = null;
    if (str_starts_with($arquivo, 'trecho:')) {
        $trecho = substr($arquivo, 7);
        if (!preg_match('/^[a-f0-9]{32}$/', $trecho)) {
            return null;
        }
        $nomeCache = 'trecho-' . $trecho;
    } elseif (preg_match('/^[A-Za-z0-9_-]{10,100}$/', $arquivo)) {
        $nomeCache = $arquivo;
    } else {
        return null;
    }

    $dir = leitura_dir_privado() . '/leitura-cache';
    if (!is_dir($dir) && !@mkdir($dir, 0750, true)) {
        return null;
    }
    leitura_limpar_cache($dir);

    $pdf = $dir . '/' . $nomeCache . '.pdf';
    if (is_readable($pdf) && filesize($pdf) > 0) {
        return $pdf;
    }

    if ($trecho !== null) {
        $url = leitura_repasse_url('trecho', $trecho);
        if ($url === null) {
            return null;
        }
        $origem = 'trecho ' . $trecho . ' (repasse)';
    } else {
        $url = 'https://drive.usercontent.google.com/download?id=' . rawurlencode($arquivo) . '&export=download&confirm=t';
        $origem = $arquivo . ' do Drive';
    }

    $status = leitura_baixar($url, $pdf, '%PDF-');
    if ($status !== 200) {
        leitura_log('falha ao baixar ' . $origem . ' (HTTP ' . $status . ')');
        return null;
    }
    file_put_contents($dir . '/' . $nomeCache . '.json', json_encode(['ate' => (int) $dados['e']]));
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
