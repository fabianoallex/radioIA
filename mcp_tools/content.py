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
    _fonte_info,
    _scan_day,
)


@mcp.tool()
def status_geracao() -> str:
    """
    Retorna o estado atual da geracao de episodios.

    Util para monitorar episodios iniciados pelo scheduler em background —
    principalmente durante a janela entre o disparo de um horario agendado
    e o aparecimento do episodio finalizado no player.

    O arquivo geracao_status.json e atualizado pelo gerador a cada etapa.
    Se nao existe, nenhuma geracao foi registrada nesta sessao.

    Etapas possiveis:
        buscando   — buscando conteudo na fonte
        llm        — gerando roteiro com o LLM
        tts        — sintetizando audio (TTS)
        mixando    — mixando audio final
        finalizando — salvando metadados
        concluido  — episodio pronto (ativo: false)
        erro       — falha durante a geracao (ativo: false)

    Quando ativo=false e etapa=concluido, use listar_episodios() para
    confirmar que o episodio esta disponivel no player.

    Se ativo=true e o campo 'aviso' aparecer, o processo pode ter encerrado
    sem registrar conclusao — verifique o scheduler.log.
    """
    status_path = os.path.join(PROJECT_DIR, 'geracao_status.json')

    if not os.path.exists(status_path):
        return json.dumps({
            'ativo':    False,
            'mensagem': 'Nenhuma geracao registrada nesta sessao.',
        }, ensure_ascii=False, indent=2)

    try:
        with open(status_path, 'r', encoding='utf-8') as f:
            status = json.load(f)
    except Exception as e:
        return json.dumps({'ativo': False, 'erro': str(e)}, ensure_ascii=False, indent=2)

    if status.get('ativo'):
        try:
            from datetime import datetime as _dt
            updated_str = status.get('atualizado', '')
            if updated_str:
                now = _dt.now()
                upd = _dt.strptime(updated_str, '%H:%M:%S').replace(
                    year=now.year, month=now.month, day=now.day)
                age_min = (now - upd).total_seconds() / 60
                if age_min > 15:
                    status['aviso'] = (
                        f'Status sem atualizacao ha {int(age_min)} minutos — '
                        'o processo pode ter encerrado sem registrar conclusao. '
                        'Verifique o scheduler.log.'
                    )
        except Exception:
            pass
        status['dica'] = 'Geracao em andamento. Chame novamente em alguns segundos para acompanhar.'
    elif status.get('etapa') == 'concluido':
        status['dica'] = 'Episodio concluido. Use listar_episodios() para ver os detalhes.'
    elif status.get('etapa') == 'erro':
        status['dica'] = 'Houve um erro. Verifique o campo erro e o scheduler.log para detalhes.'

    return json.dumps(status, ensure_ascii=False, indent=2)


@mcp.tool()
def listar_modelos() -> str:
    """
    Lista os modelos LLM disponiveis para uso nesta instalacao do RadioIA.
    Os modelos sao definidos em llm.modelos no config.yaml pelo administrador.

    Use esta ferramenta antes de chamar gerar_episodios() ou gerar_clipping()
    com um model especifico para garantir que o modelo esta disponivel e
    entender quando usar cada um (ver campo 'descricao').

    Se llm.modelos nao estiver configurado, retorna apenas o modelo padrao atual.
    """
    config  = _load_config()
    llm_cfg = config.get('llm', {})
    default = llm_cfg.get('model', 'claude-sonnet-4-6')
    modelos = llm_cfg.get('modelos', [])

    if not modelos:
        return json.dumps({
            'modelo_padrao': default,
            'modelos':       [{'id': default, 'descricao': 'modelo padrao (llm.modelos nao configurado)'}],
            'aviso':         'Configure llm.modelos no config.yaml para restringir e documentar os modelos disponiveis.',
        }, ensure_ascii=False, indent=2)

    ids = [m['id'] for m in modelos]
    return json.dumps({
        'modelo_padrao': default,
        'modelos':       modelos,
        'ids':           ids,
        'dica':          'Passe model="<id>" em gerar_episodios() ou gerar_clipping() para usar um modelo especifico.',
    }, ensure_ascii=False, indent=2)


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
            'itens_ja_citados':  len(seen_ids),
            'episodios_gerados': episodios_gerados,
        },
        'dica': 'Use gerar_episodios(["youtube", "musica:2", "noticias"]) para gerar episodios.'
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def gerar_episodios(fontes: list[str], model: str = '') -> str:
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
        fontes: Lista de IDs de fontes a gerar. Exemplos:
                ["youtube"] — so o feed do YouTube
                ["utilidades", "youtube", "noticias"] — grade completa
                ["musica:3"] — bloco musical com 3 faixas
                ["url:https://exemplo.com/artigo"] — episodio a partir de URL
                ["url:https://youtu.be/ID"] — episodio de video do YouTube (usa transcricao)
                ["url:https://a.com,https://b.com"] — episodio comparando duas URLs
                ["url:https://a.com|foca nos impactos economicos"] — URL com contexto
                ["url:https://a.com,https://b.com|compare as abordagens"] — multi-URL com contexto
        model:  Modelo LLM para esta geracao (ex: "claude-haiku-4-5-20251001").
                Sobrescreve o modelo de cada fonte apenas para esta chamada — sem alterar config.yaml.
                Se vazio, usa o modelo configurado em cada fonte ou em llm.model.

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
            path, log, err = _capture(radio_main._run_combined_source, source_cfg, config, credentials, seen_ids, first_of_day)
        else:
            path, log, err = _capture(radio_main._run_source, source_cfg, config, credentials, seen_ids, first_of_day)

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
                'fonte':   source_id,
                'status':  'ok',
                'nome':    meta.get('source_name', source_id),
                'duracao': f"{mins}m {secs}s",
                'itens':   meta.get('videos_covered', 0),
                'arquivo': path,
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
        output_dir = os.path.join(PROJECT_DIR, 'output')
        datas = []
        if os.path.exists(output_dir):
            datas = sorted([
                d for d in os.listdir(output_dir)
                if os.path.isdir(os.path.join(output_dir, d)) and d[:4].isdigit()
            ], reverse=True)
        return json.dumps({
            'data':      data,
            'episodios': [],
            'mensagem':  f"Nenhum episodio encontrado para {data}.",
            'datas_disponiveis': datas[:10],
        }, ensure_ascii=False, indent=2)

    total_dur = sum(e['duracao_seg'] for e in episodes)
    mins, secs = total_dur // 60, total_dur % 60

    return json.dumps({
        'data':            data,
        'total_episodios': len(episodes),
        'duracao_total':   f"{mins}m {secs}s",
        'player_url':      'http://localhost:5000',
        'episodios':       episodes,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def ler_episodio(pasta: str, data: str = '') -> str:
    """
    Le o conteudo completo de um episodio: roteiro (script.txt) e metadados (episode.json).
    Util para revisar o que foi gerado, verificar qualidade ou depurar problemas.

    Args:
        pasta: Nome ou prefixo parcial da pasta do episodio. Exemplos:
               "09-30_youtube"  — episodio exato
               "09-30"          — qualquer episodio das 09:30
               "youtube"        — qualquer episodio de youtube
               "noticias"       — qualquer episodio de noticias
        data: Data no formato YYYY-MM-DD. Se vazio, usa hoje.
    """
    if not data:
        data = datetime.now().strftime('%Y-%m-%d')

    day_dir = os.path.join(PROJECT_DIR, 'output', data)
    if not os.path.isdir(day_dir):
        return json.dumps({'status': 'erro', 'mensagem': f"Nenhum episodio encontrado para {data}."}, ensure_ascii=False)

    candidatos = [
        f for f in sorted(os.listdir(day_dir))
        if pasta.lower() in f.lower() and os.path.isdir(os.path.join(day_dir, f))
    ]

    if not candidatos:
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Nenhuma pasta com '{pasta}' em {data}.",
            'pastas_disponiveis': [
                f for f in sorted(os.listdir(day_dir))
                if os.path.isdir(os.path.join(day_dir, f))
            ],
        }, ensure_ascii=False, indent=2)

    resultados = []
    for folder in candidatos:
        ep_path = os.path.join(day_dir, folder)

        meta = {}
        meta_path = os.path.join(ep_path, 'episode.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

        script = ''
        script_path = os.path.join(ep_path, 'script.txt')
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                script = f.read()

        dur = meta.get('duration_seconds', 0)
        resultados.append({
            'pasta':     folder,
            'data':      data,
            'nome':      meta.get('source_name', ''),
            'duracao':   f"{dur // 60}m {dur % 60}s",
            'itens':     meta.get('videos_covered', 0),
            'metadados': meta,
            'script':    script,
        })

    if len(resultados) == 1:
        return json.dumps({'status': 'ok', **resultados[0]}, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':      'ok',
        'encontrados': len(resultados),
        'episodios':   resultados,
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
        'status':              'ok',
        'itens_removidos':     len(dados_anteriores.get('seen_ids', [])),
        'episodios_removidos': len(dados_anteriores.get('episodes', [])),
        'mensagem':            'Historico limpo. Todos os conteudos estao elegiveis novamente.',
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
