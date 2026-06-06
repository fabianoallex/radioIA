"""
RadioIA MCP Server
Expoe ferramentas para que agentes de IA gerem episodios de radio.
"""

import contextlib
import io
import json
import os
import sys
from datetime import datetime

# Setup: project dir e path antes de qualquer import local
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

import yaml
from mcp.server.fastmcp import FastMCP

import main as radio_main
from src.history import load_seen_ids

mcp = FastMCP(
    "RadioIA",
    description="Gera episodios de radio personalizados a partir de feeds do YouTube, noticias, musica e utilidades."
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    with open(os.path.join(PROJECT_DIR, 'config.yaml'), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _capture(func, *args, **kwargs):
    """Executa func capturando stdout. Retorna (resultado, log)."""
    buf = io.StringIO()
    result = None
    error = None
    try:
        with contextlib.redirect_stdout(buf):
            result = func(*args, **kwargs)
    except Exception as e:
        error = str(e)
        buf.write(f"\nERRO: {e}")
    return result, buf.getvalue(), error


def _parse_fonte(arg: str) -> tuple[str, str | None]:
    """'musica:3' -> ('musica', '3') | 'youtube' -> ('youtube', None)"""
    if ':' in arg:
        sid, param = arg.split(':', 1)
        return sid.strip(), param.strip()
    return arg.strip(), None


def _fonte_info(s: dict, seen_ids: set) -> dict:
    return {
        'id':          s['id'],
        'nome':        s['name'],
        'tipo':        s['type'],
        'habilitada':  s.get('enabled', True),
    }


def _has_audio(ep_path: str) -> bool:
    """Verifica se a pasta tem episódio (mp3 direto ou replay via audio_path)."""
    if os.path.exists(os.path.join(ep_path, 'episode.mp3')):
        return True
    meta_path = os.path.join(ep_path, 'episode.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return bool(json.load(f).get('audio_path'))
        except Exception:
            pass
    return False


def _scan_day(date_str: str) -> list[dict]:
    day_dir = os.path.join(PROJECT_DIR, 'output', date_str)
    episodes = []
    if not os.path.isdir(day_dir):
        return episodes
    for ep_folder in sorted(os.listdir(day_dir)):
        ep_path = os.path.join(day_dir, ep_folder)
        if not os.path.isdir(ep_path) or not _has_audio(ep_path):
            continue
        meta = {}
        meta_path = os.path.join(ep_path, 'episode.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        parts = ep_folder.split('_', 1)
        ep = {
            'pasta':       ep_folder,
            'horario':     parts[0],
            'fonte':       parts[1] if len(parts) > 1 else ep_folder,
            'nome':        meta.get('source_name', ''),
            'duracao_seg': meta.get('duration_seconds', 0),
            'itens':       meta.get('videos_covered', 0),
            'arquivo':     os.path.join(day_dir, ep_folder, 'episode.mp3'),
        }
        if meta.get('replay_of'):
            ep['replay_de'] = meta['replay_of']
        episodes.append(ep)
    return episodes


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def listar_fontes() -> str:
    """
    Lista todas as fontes de conteudo configuradas no RadioIA.
    Mostra id, nome, tipo, se esta habilitada e quantos itens ja foram citados no historico.
    """
    config   = _load_config()
    seen_ids = load_seen_ids()

    fontes = [_fonte_info(s, seen_ids) for s in config.get('sources', [])]

    history_path = os.path.join(PROJECT_DIR, 'history.json')
    episodios_gerados = 0
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            h = json.load(f)
        episodios_gerados = len(h.get('episodes', []))

    return json.dumps({
        'fontes': fontes,
        'historico': {
            'itens_ja_citados': len(seen_ids),
            'episodios_gerados': episodios_gerados,
        },
        'dica': 'Use gerar_episodios(["youtube", "musica:2", "noticias"]) para gerar episodios.'
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def gerar_episodios(fontes: list[str]) -> str:
    """
    Gera episodios de audio para as fontes especificadas.

    Args:
        fontes: Lista de IDs de fontes a gerar. Exemplos:
                ["youtube"] — so o feed do YouTube
                ["utilidades", "youtube", "noticias"] — grade completa
                ["musica:1"] — 1 musica
                ["musica:3"] — 3 musicas
                ["url:https://exemplo.com/artigo"] — episodio a partir de URL avulsa

    Fontes disponiveis: youtube, noticias, noticias-locais, tecnologia, horoscopo,
    utilidades, loteria, copa, brasileirao, champions, efemerides, quiz, reddit,
    receitas, filmes, filmes-cartaz, musica, musica-local, concursos, biblia.
    Para musica, use musica:N onde N e o numero de faixas (ex: musica:3).
    Para URL avulsa, use url:https://... — nao requer configuracao previa.
    """
    config      = _load_config()
    all_sources = config.get('sources', [])
    seen_ids    = load_seen_ids()
    credentials = radio_main._get_oauth_credentials()
    first_of_day = not radio_main._has_episodes_today()

    results  = []
    logs_all = []

    for arg in fontes:
        source_id, param = _parse_fonte(arg)

        # Fonte de URL avulsa: sintética, sem entrada no config
        if source_id == 'url' and param:
            source_cfg = {
                'id': 'url', 'type': 'url',
                'name': 'Conteudo da Web',
                'settings': {'url': param},
            }
        else:
            source_cfg = next((s for s in all_sources if s['id'] == source_id), None)
            if not source_cfg:
                results.append({'fonte': source_id, 'status': 'erro', 'mensagem': f"Fonte '{source_id}' nao encontrada."})
                continue

        source_type = source_cfg.get('type')

        # Aplicar override de param (ex: musica:3)
        if param and source_type == 'music':
            try:
                n = int(param)
                source_cfg = {**source_cfg, 'settings': {**source_cfg.get('settings', {}), 'num_tracks': n}}
            except ValueError:
                pass

        # Executar fonte com captura de stdout
        if source_type == 'music':
            path, log, err = _capture(radio_main._run_music_source, source_cfg, config, first_of_day)
        elif source_type == 'utility':
            path, log, err = _capture(radio_main._run_utility_source, source_cfg, config, first_of_day)
        else:
            path, log, err = _capture(radio_main._run_source, source_cfg, config, credentials, seen_ids, first_of_day)

        logs_all.append(f"[{source_id}]\n{log.strip()}")

        if path and os.path.exists(path):
            # Ler metadados do episodio gerado
            meta_path = os.path.join(os.path.dirname(path), 'episode.json')
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)

            dur = meta.get('duration_seconds', 0)
            mins, secs = dur // 60, dur % 60
            results.append({
                'fonte':    source_id,
                'status':   'ok',
                'nome':     meta.get('source_name', source_id),
                'duracao':  f"{mins}m {secs}s",
                'itens':    meta.get('videos_covered', 0),
                'arquivo':  path,
            })
            first_of_day = False
            seen_ids = load_seen_ids()
        else:
            results.append({
                'fonte':    source_id,
                'status':   'erro',
                'mensagem': err or 'Nenhum episodio gerado.',
            })

    gerados = [r for r in results if r['status'] == 'ok']
    falhas  = [r for r in results if r['status'] == 'erro']

    return json.dumps({
        'resumo': {
            'gerados':    len(gerados),
            'falhas':     len(falhas),
            'player_url': 'http://localhost:5000',
        },
        'episodios': results,
        'log':       '\n\n'.join(logs_all),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def listar_episodios(data: str = '') -> str:
    """
    Lista os episodios gerados para uma data especifica.

    Args:
        data: Data no formato YYYY-MM-DD. Se vazio, usa a data de hoje.
    """
    if not data:
        data = datetime.now().strftime('%Y-%m-%d')

    episodes = _scan_day(data)

    if not episodes:
        # Listar datas disponiveis
        output_dir = os.path.join(PROJECT_DIR, 'output')
        datas = []
        if os.path.exists(output_dir):
            datas = sorted([
                d for d in os.listdir(output_dir)
                if os.path.isdir(os.path.join(output_dir, d)) and d[:4].isdigit()
            ], reverse=True)
        return json.dumps({
            'data':     data,
            'episodios': [],
            'mensagem': f"Nenhum episodio encontrado para {data}.",
            'datas_disponiveis': datas[:10],
        }, ensure_ascii=False, indent=2)

    total_dur = sum(e['duracao_seg'] for e in episodes)
    mins, secs = total_dur // 60, total_dur % 60

    return json.dumps({
        'data':              data,
        'total_episodios':   len(episodes),
        'duracao_total':     f"{mins}m {secs}s",
        'player_url':        'http://localhost:5000',
        'episodios':         episodes,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def status_historico() -> str:
    """
    Mostra o status do historico de episodios gerados.
    O historico controla quais itens ja foram citados para evitar repeticao.
    """
    history_path = os.path.join(PROJECT_DIR, 'history.json')
    if not os.path.exists(history_path):
        return json.dumps({'itens_vistos': 0, 'episodios': 0, 'mensagem': 'Historico vazio.'}, ensure_ascii=False)

    with open(history_path, 'r', encoding='utf-8') as f:
        h = json.load(f)

    episodios = h.get('episodes', [])
    ultimo = episodios[-1] if episodios else None

    return json.dumps({
        'itens_vistos':    len(h.get('seen_ids', [])),
        'episodios_total': len(episodios),
        'ultimo_episodio': ultimo['episode_id'] if ultimo else None,
        'dica': 'Use limpar_historico() para resetar e permitir repeticao de conteudos.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def limpar_historico() -> str:
    """
    Limpa o historico de episodios gerados.
    Apos limpar, todos os conteudos ficam elegiveis novamente para novos episodios.
    """
    history_path = os.path.join(PROJECT_DIR, 'history.json')
    dados_anteriores = {'seen_ids': [], 'episodes': []}

    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            dados_anteriores = json.load(f)

    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump({'seen_ids': [], 'episodes': []}, f, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':           'ok',
        'itens_removidos':  len(dados_anteriores.get('seen_ids', [])),
        'episodios_removidos': len(dados_anteriores.get('episodes', [])),
        'mensagem':         'Historico limpo. Todos os conteudos estao elegiveis novamente.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def replay_episodio(parcial: str, data: str = '') -> str:
    """
    Cria um replay de episodios cujas pastas batem com o prefixo parcial.
    Nao regera o audio — apenas registra o episodio original no horario atual
    para que o player o exiba e reproduza.

    Args:
        parcial: Prefixo parcial do nome da pasta do episodio. Exemplos:
                 "12-15"       — todos os episodios gerados as 12:15
                 "12-15_not"   — episodio das 12:15 cuja pasta comeca com "12-15_not"
                 "noticias"    — qualquer episodio de noticias (sem filtro de horario)
        data: Data no formato YYYY-MM-DD. Se vazio, usa hoje.

    Equivalente a: python main.py replay:12-15_not
    """
    if not data:
        data = datetime.now().strftime('%Y-%m-%d')

    import contextlib, io as _io
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        paths = radio_main._run_replay_cli(parcial, today=data)
    log = buf.getvalue()

    if not paths:
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Nenhum episodio encontrado com prefixo '{parcial}' em {data}.",
            'log':      log,
        }, ensure_ascii=False, indent=2)

    replays = []
    for p in paths:
        meta = {}
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        replays.append({
            'pasta':      os.path.basename(os.path.dirname(p)),
            'replay_de':  meta.get('replay_of', ''),
            'nome':       meta.get('source_name', ''),
        })

    return json.dumps({
        'status':          'ok',
        'data':            data,
        'replays_criados': len(replays),
        'replays':         replays,
        'player_url':      'http://localhost:5000',
        'log':             log,
    }, ensure_ascii=False, indent=2)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    mcp.run()
