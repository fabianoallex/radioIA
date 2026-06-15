import json
import os
from datetime import datetime

from mcp_tools._instance import mcp
from mcp_tools._utils import PROJECT_DIR, _load_config, _save_config

_SPOTS_CACHE_DIR = os.path.join(PROJECT_DIR, 'output', '_spots')


def _spot_cache_info(spot: dict) -> dict:
    """Retorna info de cache para um spot."""
    sid   = spot['id']
    stype = spot.get('type', 'file')
    today = datetime.now().strftime('%Y-%m-%d')

    if stype == 'file':
        path = spot.get('path', '')
        return {
            'tipo_cache': 'arquivo_externo',
            'path':       path,
            'existe':     os.path.exists(path) if path else False,
        }

    if stype == 'tts':
        cache  = os.path.join(_SPOTS_CACHE_DIR, f"{sid}.mp3")
        exists = os.path.exists(cache)
        info   = {'tipo_cache': 'permanente', 'arquivo': cache, 'existe': exists}
        if exists:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache)).strftime('%Y-%m-%d %H:%M')
            info['gerado_em']   = mtime
            info['tamanho_kb']  = round(os.path.getsize(cache) / 1024, 1)
        return info

    if stype == 'llm':
        cache_mp3 = os.path.join(_SPOTS_CACHE_DIR, f"{sid}-{today}.mp3")
        cache_txt = os.path.join(_SPOTS_CACHE_DIR, f"{sid}-{today}.txt")
        exists    = os.path.exists(cache_mp3)
        info      = {'tipo_cache': 'diario', 'arquivo_hoje': cache_mp3, 'existe_hoje': exists}
        if exists:
            info['tamanho_kb'] = round(os.path.getsize(cache_mp3) / 1024, 1)
        if os.path.exists(cache_txt):
            with open(cache_txt, 'r', encoding='utf-8') as f:
                info['script_hoje'] = f.read()
        if os.path.exists(_SPOTS_CACHE_DIR):
            anteriores = sorted([
                f for f in os.listdir(_SPOTS_CACHE_DIR)
                if f.startswith(f"{sid}-") and f.endswith('.mp3') and today not in f
            ], reverse=True)
            info['caches_anteriores'] = anteriores[:5]
        return info

    return {'tipo_cache': 'desconhecido'}


@mcp.tool()
def adicionar_spot(
    id_spot: str,
    tipo: str,
    texto: str = '',
    topico: str = '',
    path: str = '',
    peso: int = 1,
    max_por_dia: int = None,
    voz: str = '',
    duracao_seg: int = 20,
    modelo: str = '',
) -> str:
    """
    Adiciona um novo spot ao config.yaml.

    ATENCAO: salvar o config reformata o YAML e perde os comentarios do arquivo.

    Args:
        id_spot:     ID unico do spot (ex: "aviso-reuniao", "promo-produto").
        tipo:        Tipo do spot: "tts" | "llm" | "file"
                     tts  — texto fixo convertido em voz (cache permanente)
                     llm  — topico gerado diariamente pelo LLM (cache diario)
                     file — arquivo MP3 externo pre-gravado
        texto:       Texto a narrar. Obrigatorio para tipo "tts".
        topico:      Tema para o LLM criar o script. Obrigatorio para tipo "llm".
        path:        Caminho do arquivo MP3. Obrigatorio para tipo "file".
        peso:        Frequencia relativa de rotacao (padrao: 1).
        max_por_dia: Limite de reproducoes por dia. Omitir = sem limite.
        voz:         Voz edge-tts a usar (omitir = usa vinheta.voice do config).
        duracao_seg: Duracao alvo em segundos para spots llm (padrao: 20).
        modelo:      Modelo LLM para spots llm (omitir = usa llm.model do config).

    Exemplos:
        adicionar_spot("aviso-reuniao", "tts", texto="Reuniao geral as 15h.")
        adicionar_spot("promo-produto", "llm", topico="Promova o produto X em 20s", duracao_seg=20)
        adicionar_spot("jingle", "file", path="spots/jingle.mp3", peso=2)
    """
    if not id_spot or not tipo:
        return json.dumps({'status': 'erro', 'mensagem': 'id_spot e tipo sao obrigatorios.'}, ensure_ascii=False)

    tipo = tipo.lower()
    if tipo not in ('tts', 'llm', 'file'):
        return json.dumps({'status': 'erro', 'mensagem': 'tipo deve ser: tts | llm | file'}, ensure_ascii=False)

    if tipo == 'tts' and not texto:
        return json.dumps({'status': 'erro', 'mensagem': 'Para tipo "tts", o campo texto e obrigatorio.'}, ensure_ascii=False)
    if tipo == 'llm' and not topico:
        return json.dumps({'status': 'erro', 'mensagem': 'Para tipo "llm", o campo topico e obrigatorio.'}, ensure_ascii=False)
    if tipo == 'file' and not path:
        return json.dumps({'status': 'erro', 'mensagem': 'Para tipo "file", o campo path e obrigatorio.'}, ensure_ascii=False)

    config = _load_config()
    spots  = config.get('spots') or []

    if any(s['id'] == id_spot for s in spots):
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Spot '{id_spot}' ja existe. Use deletar_cache_spot() + remover_spot() para substituir.",
        }, ensure_ascii=False, indent=2)

    spot: dict = {'id': id_spot, 'type': tipo}

    if tipo == 'tts':
        spot['text'] = texto
        if voz:
            spot['voice'] = voz
    elif tipo == 'llm':
        spot['topic']            = topico
        spot['duration_seconds'] = duracao_seg
        if modelo:
            spot['model'] = modelo
        if voz:
            spot['voice'] = voz
    elif tipo == 'file':
        spot['path'] = path

    if peso != 1:
        spot['weight'] = peso
    if max_por_dia is not None:
        spot['max_per_day'] = max_por_dia

    spots.append(spot)
    config['spots'] = spots
    _save_config(config)

    return json.dumps({
        'status':        'ok',
        'spot':          spot,
        'total_spots':   len(spots),
        'proximo_passo': 'Use gerar_spot("' + id_spot + '") para pre-gerar o audio.' if tipo in ('tts', 'llm') else '',
        'aviso':         'config.yaml foi reformatado — comentarios originais foram perdidos.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def remover_spot(id_spot: str) -> str:
    """
    Remove um spot do config.yaml.
    O cache de audio NAO e removido automaticamente — use deletar_cache_spot() se necessario.

    Args:
        id_spot: ID do spot a remover.
    """
    config = _load_config()
    spots  = config.get('spots') or []

    removido = next((s for s in spots if s['id'] == id_spot), None)
    if not removido:
        ids = [s['id'] for s in spots]
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Spot '{id_spot}' nao encontrado.",
            'spots_disponiveis': ids,
        }, ensure_ascii=False, indent=2)

    config['spots'] = [s for s in spots if s['id'] != id_spot]
    _save_config(config)

    return json.dumps({
        'status':          'ok',
        'removido':        removido,
        'total_restantes': len(config['spots']),
        'dica':            f'Cache de audio nao removido. Use deletar_cache_spot("{id_spot}") se quiser limpar.',
        'aviso':           'config.yaml foi reformatado — comentarios originais foram perdidos.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def gerar_spot(id_spot: str, forcar: bool = False) -> str:
    """
    Gera ou atualiza o audio cacheado de um spot tts ou llm.
    Spots do tipo 'file' nao precisam de geracao — apontam para MP3 externo.

    Args:
        id_spot: ID do spot a gerar (conforme configurado em config.yaml).
        forcar:  Se True, apaga o cache existente e regenera mesmo que ja exista.
                 Para spots llm, util para obter um novo script no mesmo dia.
                 Default: False (so gera se o cache nao existir).

    Exemplos:
        gerar_spot("aviso-reuniao")            — gera se ainda nao existe
        gerar_spot("chamada-produto", forcar=True) — regenera mesmo que ja exista
    """
    config = _load_config()
    spots  = config.get('spots') or []
    spot   = next((s for s in spots if s['id'] == id_spot), None)

    if not spot:
        ids = [s['id'] for s in spots]
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Spot '{id_spot}' nao encontrado.",
            'spots_disponiveis': ids,
        }, ensure_ascii=False, indent=2)

    stype = spot.get('type', 'file')

    if stype == 'file':
        path = spot.get('path', '')
        return json.dumps({
            'status':   'nao_aplicavel',
            'mensagem': f"Spot '{id_spot}' e do tipo 'file' — aponta para arquivo externo.",
            'path':     path,
            'existe':   os.path.exists(path),
        }, ensure_ascii=False, indent=2)

    if forcar:
        today = datetime.now().strftime('%Y-%m-%d')
        if stype == 'tts':
            cache = os.path.join(_SPOTS_CACHE_DIR, f"{id_spot}.mp3")
            if os.path.exists(cache):
                os.remove(cache)
        elif stype == 'llm':
            for f in os.listdir(_SPOTS_CACHE_DIR) if os.path.exists(_SPOTS_CACHE_DIR) else []:
                if f.startswith(f"{id_spot}-{today}"):
                    os.remove(os.path.join(_SPOTS_CACHE_DIR, f))

    from src.spots import _get_audio
    audio = _get_audio(spot, config)

    if not audio:
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Falha ao gerar audio para o spot '{id_spot}'.",
        }, ensure_ascii=False, indent=2)

    cache_info = _spot_cache_info(spot)
    resultado = {
        'status':     'ok',
        'id':         id_spot,
        'tipo':       stype,
        'forcado':    forcar,
        'tamanho_kb': cache_info.get('tamanho_kb'),
        'arquivo':    cache_info.get('arquivo') or cache_info.get('arquivo_hoje'),
    }
    if stype == 'llm' and cache_info.get('script_hoje'):
        resultado['script_gerado'] = cache_info['script_hoje']

    return json.dumps(resultado, ensure_ascii=False, indent=2)


@mcp.tool()
def deletar_cache_spot(id_spot: str) -> str:
    """
    Apaga o audio cacheado de um spot para forcara regeneracao na proxima vez que tocar.
    Util quando o texto ou topico de um spot e alterado no config.yaml.

    Para spots 'tts': remove output/_spots/{id}.mp3
    Para spots 'llm': remove todos os caches datados output/_spots/{id}-*.mp3 e .txt

    Args:
        id_spot: ID do spot cujo cache deve ser removido.
                 Use "*" para limpar o cache de todos os spots.
    """
    config = _load_config()
    spots  = config.get('spots') or []

    if id_spot == '*':
        alvos = [s for s in spots if s.get('type') in ('tts', 'llm')]
    else:
        spot = next((s for s in spots if s['id'] == id_spot), None)
        if not spot:
            ids = [s['id'] for s in spots]
            return json.dumps({
                'status':   'erro',
                'mensagem': f"Spot '{id_spot}' nao encontrado.",
                'spots_disponiveis': ids,
            }, ensure_ascii=False, indent=2)
        if spot.get('type') == 'file':
            return json.dumps({
                'status':   'nao_aplicavel',
                'mensagem': f"Spot '{id_spot}' e do tipo 'file' — nao ha cache para apagar.",
            }, ensure_ascii=False, indent=2)
        alvos = [spot]

    removidos = []
    erros     = []

    if not os.path.exists(_SPOTS_CACHE_DIR):
        return json.dumps({
            'status':    'ok',
            'mensagem':  'Pasta de cache vazia — nada a remover.',
            'removidos': [],
        }, ensure_ascii=False, indent=2)

    for s in alvos:
        sid   = s['id']
        stype = s.get('type')
        if stype == 'tts':
            cache = os.path.join(_SPOTS_CACHE_DIR, f"{sid}.mp3")
            if os.path.exists(cache):
                try:
                    os.remove(cache)
                    removidos.append(os.path.basename(cache))
                except Exception as e:
                    erros.append({'arquivo': cache, 'erro': str(e)})
        elif stype == 'llm':
            for fname in os.listdir(_SPOTS_CACHE_DIR):
                if fname.startswith(f"{sid}-") and (fname.endswith('.mp3') or fname.endswith('.txt')):
                    fpath = os.path.join(_SPOTS_CACHE_DIR, fname)
                    try:
                        os.remove(fpath)
                        removidos.append(fname)
                    except Exception as e:
                        erros.append({'arquivo': fpath, 'erro': str(e)})

    return json.dumps({
        'status':          'ok' if not erros else 'parcial',
        'removidos':       removidos,
        'total_removidos': len(removidos),
        'erros':           erros,
        'mensagem':        'Cache removido. Os spots serao regerados na proxima vez que tocarem.',
    }, ensure_ascii=False, indent=2)
