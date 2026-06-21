import json
import os
from datetime import datetime

import main as radio_main
from src.history import load_seen_ids

from mcp_tools._instance import mcp
from mcp_tools._utils import (
    PROJECT_DIR,
    _load_config,
    _capture,
    _parse_fonte,
)


@mcp.tool()
def gerar_episodios(fontes: list[str], model: str = '', publicar: bool = True) -> str:
    """
    Gera episodios de audio para as fontes especificadas.

    CONTEXTO ADICIONAL — instruindo o roteirista:
        Qualquer fonte aceita o sufixo |contexto para orientar o roteirista (tom, foco, angulo).
        O contexto e uma instrucao livre — nao filtra o conteudo buscado, apenas guia a narrativa.

        Exemplos:
            ["youtube|foca nos lancamentos de tecnologia desta semana"]
            ["noticias|destaque apenas noticias economicas, ignore esportes"]
            ["noticias", "tecnologia|publico jovem universitario, linguagem informal"]
            ["url:https://a.com|extraia os pontos tecnicos"]

        Alternativa persistente: campo context: na definicao da fonte em config.yaml.
        O contexto passado aqui sobrescreve o do config.yaml para aquela chamada.

    Args:
        fontes:   Lista de IDs de fontes a gerar. Exemplos:
                  ["youtube"] — so o feed do YouTube
                  ["utilidades", "youtube", "noticias"] — grade completa
                  ["musica:3"] — bloco musical com 3 faixas
                  ["url:https://exemplo.com/artigo"] — episodio a partir de URL
                  ["url:https://youtu.be/ID"] — episodio de video do YouTube (usa transcricao)
                  ["url:https://a.com,https://b.com"] — episodio comparando duas URLs
                  ["url:https://a.com|foca nos impactos economicos"] — URL com contexto
                  ["url:https://a.com,https://b.com|compare as abordagens"] — multi-URL com contexto
        model:    Modelo LLM para esta geracao (ex: "claude-haiku-4-5-20251001").
                  Sobrescreve o modelo de cada fonte apenas para esta chamada — sem alterar config.yaml.
                  Se vazio, usa o modelo configurado em cada fonte ou em llm.model.
        publicar: Se False, o episodio e gerado como rascunho (status=draft) e nao aparece no player.
                  Use publicar_episodio() para publicar depois. Padrao: True.

    URLs suportadas:
        - Qualquer pagina web: extrai texto via trafilatura, usa nome real do site e data de publicacao
        - YouTube (youtube.com/watch, youtu.be, youtube.com/shorts): usa transcricao automatica
        - Multiplas URLs separadas por virgula: gera um episodio unico integrando todas

    Fontes disponiveis: youtube, noticias, noticias-locais, tecnologia, horoscopo,
    utilidades, loteria, copa, brasileirao, champions, efemerides, quiz, reddit,
    receitas, filmes, filmes-cartaz, musica, musica-local, concursos, biblia.
    Fontes do tipo combined (ex: bom-dia) agregam multiplas sub-fontes em um unico episodio.
    """
    config      = _load_config()
    all_sources = config.get('sources', [])
    seen_ids    = load_seen_ids()
    credentials = radio_main._get_oauth_credentials()
    first_of_day = not radio_main._has_episodes_today()

    if model:
        modelos_cfg = config.get('llm', {}).get('modelos', [])
        if modelos_cfg:
            ids_permitidos = [m['id'] for m in modelos_cfg]
            if model not in ids_permitidos:
                return json.dumps({
                    'status':   'erro',
                    'mensagem': f"Modelo '{model}' nao esta na lista de modelos permitidos.",
                    'modelos_permitidos': modelos_cfg,
                    'dica':    'Use listar_modelos() para ver as opcoes disponiveis.',
                }, ensure_ascii=False, indent=2)

    results  = []
    logs_all = []

    for arg in fontes:
        source_id, param, ctx = _parse_fonte(arg)

        if source_id == 'url' and param:
            source_cfg = {
                'id': 'url', 'type': 'url',
                'name': 'Conteudo da Web',
                'settings': {'url': param.strip()},
                'context': ctx,
            }
        elif source_id == 'clipping' and param:
            base = next((s for s in all_sources if s['id'] == 'clipping'), {})
            source_cfg = {
                **base,
                'id':      'clipping',
                'type':    'clipping',
                'name':    f"Clipping — {param[:60]}",
                'enabled': True,
                'settings': {**(base.get('settings') or {}), 'topic': param},
            }
        else:
            source_cfg = next((s for s in all_sources if s['id'] == source_id), None)
            if not source_cfg:
                results.append({'fonte': source_id, 'status': 'erro', 'mensagem': f"Fonte '{source_id}' nao encontrada."})
                continue

        if ctx:
            source_cfg = {**source_cfg, 'context': ctx}

        if model:
            source_cfg = {**source_cfg, 'model': model}

        source_type = source_cfg.get('type')

        if param and source_type == 'music':
            try:
                n = int(param)
                source_cfg = {**source_cfg, 'settings': {**source_cfg.get('settings', {}), 'num_tracks': n}}
            except ValueError:
                pass

        if param and source_type not in ('music', 'utility', 'combined'):
            source_cfg = {**source_cfg, '_param': param}

        if source_type == 'music':
            path, log, err = _capture(radio_main._run_music_source, source_cfg, config, first_of_day)
        elif source_type == 'utility':
            path, log, err = _capture(radio_main._run_utility_source, source_cfg, config, first_of_day)
        elif source_type == 'combined':
            path, log, err = _capture(radio_main._run_combined_source, source_cfg, config, credentials, seen_ids, first_of_day, publish=publicar)
        else:
            path, log, err = _capture(radio_main._run_source, source_cfg, config, credentials, seen_ids, first_of_day, publish=publicar)

        logs_all.append(f"[{source_id}]\n{log.strip()}")

        if path and os.path.exists(path):
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
                'publicado': meta.get('status', 'published') == 'published',
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
        'status':              'ok',
        'itens_removidos':     len(dados_anteriores.get('seen_ids', [])),
        'episodios_removidos': len(dados_anteriores.get('episodes', [])),
        'mensagem':            'Historico limpo. Todos os conteudos estao elegiveis novamente.',
    }, ensure_ascii=False, indent=2)


def _update_episode_status(data: str, pasta: str, novo_status: str) -> dict:
    ep_json = os.path.join(PROJECT_DIR, 'output', data, pasta, 'episode.json')
    if not os.path.exists(ep_json):
        return {'status': 'erro', 'mensagem': f"episode.json nao encontrado: {data}/{pasta}"}
    with open(ep_json, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    meta['status'] = novo_status
    with open(ep_json, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return {'status': 'ok', 'episodio': f"{data}/{pasta}", 'novo_status': novo_status}


@mcp.tool()
def publicar_episodio(data: str, pasta: str) -> str:
    """
    Publica um episodio com status 'draft', tornando-o visivel no player.

    Args:
        data:  Data do episodio no formato YYYY-MM-DD. Exemplo: "2026-06-21"
        pasta: Nome da pasta do episodio. Exemplo: "08-30_youtube"
    """
    return json.dumps(_update_episode_status(data, pasta, 'published'), ensure_ascii=False, indent=2)


@mcp.tool()
def despublicar_episodio(data: str, pasta: str) -> str:
    """
    Move um episodio publicado para status 'draft', ocultando-o do player.

    Args:
        data:  Data do episodio no formato YYYY-MM-DD. Exemplo: "2026-06-21"
        pasta: Nome da pasta do episodio. Exemplo: "08-30_youtube"
    """
    return json.dumps(_update_episode_status(data, pasta, 'draft'), ensure_ascii=False, indent=2)


@mcp.tool()
def remover_episodio(data: str, pasta: str) -> str:
    """
    Remove permanentemente um episodio (pasta + audio) e limpa seus itens do historico,
    tornando o conteudo elegivel para nova geracao.

    Args:
        data:  Data do episodio no formato YYYY-MM-DD. Exemplo: "2026-06-21"
        pasta: Nome da pasta do episodio. Exemplo: "08-30_youtube"
    """
    import shutil as _shutil
    ep_dir = os.path.join(PROJECT_DIR, 'output', data, pasta)
    if not os.path.exists(ep_dir):
        return json.dumps({'status': 'erro', 'mensagem': f"Episodio nao encontrado: {data}/{pasta}"},
                          ensure_ascii=False, indent=2)

    ep_id = f"{data}/{pasta}"
    history_path = os.path.join(PROJECT_DIR, 'history.json')
    items_removed = 0
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                hist = json.load(f)
            ep_entry = next((e for e in hist.get('episodes', []) if e.get('episode_id') == ep_id), None)
            if ep_entry:
                id_set = {v['id'] for v in ep_entry.get('videos', [])}
                hist['seen_ids'] = [i for i in hist.get('seen_ids', []) if i not in id_set]
                hist['episodes'] = [e for e in hist.get('episodes', []) if e.get('episode_id') != ep_id]
                items_removed = len(id_set)
                with open(history_path, 'w', encoding='utf-8') as f:
                    json.dump(hist, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({'status': 'erro', 'mensagem': f"Erro ao limpar historico: {e}"},
                              ensure_ascii=False, indent=2)

    _shutil.rmtree(ep_dir, ignore_errors=True)
    return json.dumps({
        'status':         'ok',
        'removido':       ep_id,
        'itens_liberados': items_removed,
        'mensagem':       'Episodio removido. Os itens estao elegiveis novamente.',
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
    import contextlib as _ctx
    import io as _io

    if not data:
        data = datetime.now().strftime('%Y-%m-%d')

    buf = _io.StringIO()
    with _ctx.redirect_stdout(buf):
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
            'pasta':     os.path.basename(os.path.dirname(p)),
            'replay_de': meta.get('replay_of', ''),
            'nome':      meta.get('source_name', ''),
        })

    return json.dumps({
        'status':          'ok',
        'data':            data,
        'replays_criados': len(replays),
        'replays':         replays,
        'player_url':      'http://localhost:5000',
        'log':             log,
    }, ensure_ascii=False, indent=2)
