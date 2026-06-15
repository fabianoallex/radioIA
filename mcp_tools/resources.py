"""MCP Resources — leitura somente, expostos como dados em vez de ferramentas."""
import json
import os
from datetime import datetime

from src.history import load_seen_ids

from mcp_tools._instance import mcp
from mcp_tools._utils import (
    PROJECT_DIR,
    _load_config,
    _fonte_info,
    _scan_day,
    _schedule_entry_key,
)
from mcp_tools.spots import _spot_cache_info, _SPOTS_CACHE_DIR
from mcp_tools.system import _scheduler_status

_WELCOME_INTRO_PATH = os.path.join(PROJECT_DIR, 'output', '_welcome_intro.mp3')
_OPERACAO_FILE      = os.path.join(PROJECT_DIR, 'OPERACAO.md')


# ── briefing ──────────────────────────────────────────────────────────────────

@mcp.resource("radioia://briefing")
def resource_briefing() -> str:
    """Snapshot operacional completo: radio, scheduler, player, episodios de hoje, proximos agendamentos e notas."""
    resultado: dict = {}

    config = _load_config()
    radio  = config.get('radio', {})
    resultado['radio'] = {
        'nome':            radio.get('name', 'RadioIA'),
        'llm_model':       config.get('llm', {}).get('model', ''),
        'tts_provider':    config.get('tts', {}).get('provider', 'edge_tts'),
        'narradores':      [n.get('name') for n in config.get('narrators', [])],
        'fontes_ativas':   [s['id'] for s in config.get('sources', []) if s.get('enabled', True)],
        'fontes_inativas': [s['id'] for s in config.get('sources', []) if not s.get('enabled', True)],
        'spots':           [s['id'] for s in (config.get('spots') or [])],
    }

    resultado['scheduler'] = _scheduler_status()

    import urllib.request
    player_ativo = False
    try:
        urllib.request.urlopen('http://localhost:5000', timeout=2)
        player_ativo = True
    except Exception:
        pass
    resultado['player'] = {'ativo': player_ativo, 'url': 'http://localhost:5000'}

    faltando = [
        k for k in ('ANTHROPIC_API_KEY', 'YOUTUBE_API_KEY')
        if not os.environ.get(k)
    ]
    resultado['api_keys_faltando'] = faltando

    hoje = datetime.now().strftime('%Y-%m-%d')
    eps_hoje  = _scan_day(hoje)
    total_dur = sum(e['duracao_seg'] for e in eps_hoje)
    resultado['hoje'] = {
        'data':            hoje,
        'total_episodios': len(eps_hoje),
        'duracao_total':   f"{total_dur // 3600}h {(total_dur % 3600) // 60}m",
        'ultimo_episodio': eps_hoje[-1]['pasta'] if eps_hoje else None,
    }

    now_time = datetime.now().strftime('%H:%M')
    state_path = os.path.join(PROJECT_DIR, 'scheduler_state.json')
    state = {}
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
    completed_today = set(state.get('completed_today', {}).keys())

    proximos = []
    for entry in config.get('schedule', []):
        if (not entry.get('date')
                and entry.get('time', '') >= now_time
                and f"{hoje}|{_schedule_entry_key(entry)}" not in completed_today):
            proximos.append({
                'time':    entry['time'],
                'label':   entry.get('label', ''),
                'sources': entry.get('sources', [f"replay:{entry['replay_of']}"
                                                  if entry.get('replay_of') is not None
                                                  else '']),
            })
            if len(proximos) >= 5:
                break
    resultado['proximos_agendamentos'] = proximos

    history_path = os.path.join(PROJECT_DIR, 'history.json')
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            h = json.load(f)
        resultado['historico'] = {
            'itens_vistos':    len(h.get('seen_ids', [])),
            'episodios_total': len(h.get('episodes', [])),
        }

    if os.path.exists(_OPERACAO_FILE):
        with open(_OPERACAO_FILE, 'r', encoding='utf-8') as f:
            resultado['notas_operacionais'] = f.read()
    else:
        resultado['notas_operacionais'] = (
            'Nenhuma nota registrada ainda. '
            'Use registrar_nota("texto", "categoria") para registrar conhecimento operacional.'
        )

    resultado['dica'] = (
        'Para registrar aprendizados desta sessao, use registrar_nota(). '
        'Essas notas ficam no projeto e estao disponiveis em qualquer sessao futura.'
    )

    return json.dumps(resultado, ensure_ascii=False, indent=2)


# ── fontes ────────────────────────────────────────────────────────────────────

@mcp.resource("radioia://fontes")
def resource_fontes() -> str:
    """Lista todas as fontes de conteudo configuradas: id, nome, tipo, status e historico."""
    config   = _load_config()
    seen_ids = load_seen_ids()
    fontes   = [_fonte_info(s, seen_ids) for s in config.get('sources', [])]

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
        'dica': 'Use gerar_episodios(["youtube", "musica:2", "noticias"]) para gerar episodios.',
    }, ensure_ascii=False, indent=2)


# ── modelos ───────────────────────────────────────────────────────────────────

@mcp.resource("radioia://modelos")
def resource_modelos() -> str:
    """Modelos LLM disponiveis e modelo padrao configurado em llm.modelos do config.yaml."""
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

    return json.dumps({
        'modelo_padrao': default,
        'modelos':       modelos,
        'ids':           [m['id'] for m in modelos],
        'dica':          'Passe model="<id>" em gerar_episodios() ou gerar_clipping() para usar um modelo especifico.',
    }, ensure_ascii=False, indent=2)


# ── historico ─────────────────────────────────────────────────────────────────

@mcp.resource("radioia://historico")
def resource_historico() -> str:
    """Status do historico de episodios: itens vistos e total gerado."""
    history_path = os.path.join(PROJECT_DIR, 'history.json')
    if not os.path.exists(history_path):
        return json.dumps({'itens_vistos': 0, 'episodios': 0, 'mensagem': 'Historico vazio.'}, ensure_ascii=False)

    with open(history_path, 'r', encoding='utf-8') as f:
        h = json.load(f)

    episodios = h.get('episodes', [])
    ultimo    = episodios[-1] if episodios else None

    return json.dumps({
        'itens_vistos':    len(h.get('seen_ids', [])),
        'episodios_total': len(episodios),
        'ultimo_episodio': ultimo['episode_id'] if ultimo else None,
        'dica':            'Use limpar_historico() para resetar e permitir repeticao de conteudos.',
    }, ensure_ascii=False, indent=2)


# ── geracao ───────────────────────────────────────────────────────────────────

@mcp.resource("radioia://geracao")
def resource_geracao() -> str:
    """Estado atual da geracao de episodios (le geracao_status.json)."""
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
            updated_str = status.get('atualizado', '')
            if updated_str:
                now = datetime.now()
                upd = datetime.strptime(updated_str, '%H:%M:%S').replace(
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
        status['dica'] = 'Geracao em andamento. Leia novamente em alguns segundos para acompanhar.'
    elif status.get('etapa') == 'concluido':
        status['dica'] = 'Episodio concluido. Leia radioia://episodios para ver os detalhes.'
    elif status.get('etapa') == 'erro':
        status['dica'] = 'Houve um erro. Verifique o campo erro e leia radioia://log para detalhes.'

    return json.dumps(status, ensure_ascii=False, indent=2)


# ── episodios ─────────────────────────────────────────────────────────────────

@mcp.resource("radioia://episodios")
def resource_episodios_hoje() -> str:
    """Episodios gerados hoje."""
    return _episodios_data(datetime.now().strftime('%Y-%m-%d'))


@mcp.resource("radioia://episodios/{data}")
def resource_episodios(data: str) -> str:
    """Episodios gerados para a data informada (YYYY-MM-DD)."""
    return _episodios_data(data)


def _episodios_data(data: str) -> str:
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
    return json.dumps({
        'data':            data,
        'total_episodios': len(episodes),
        'duracao_total':   f"{total_dur // 60}m {total_dur % 60}s",
        'player_url':      'http://localhost:5000',
        'episodios':       episodes,
    }, ensure_ascii=False, indent=2)


@mcp.resource("radioia://episodio/{data}/{pasta}")
def resource_episodio(data: str, pasta: str) -> str:
    """Roteiro e metadados de um episodio. data=YYYY-MM-DD, pasta=nome ou prefixo parcial."""
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


# ── grade ─────────────────────────────────────────────────────────────────────

@mcp.resource("radioia://grade")
def resource_grade() -> str:
    """Grade completa de programacao: horarios, fontes, labels, slot_ids, replays e status de execucao."""
    config   = _load_config()
    entries  = config.get('schedule', [])
    today    = datetime.now().strftime('%Y-%m-%d')
    now_time = datetime.now().strftime('%H:%M')

    state_path = os.path.join(PROJECT_DIR, 'scheduler_state.json')
    state = {}
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)

    completed_today = set(state.get('completed_today', {}).keys())
    completed_once  = set(state.get('completed_once', []))

    grade       = []
    proximo_idx = None

    for i, entry in enumerate(entries):
        e = {
            'time':  entry.get('time', ''),
            'label': entry.get('label', ''),
            'tipo':  'pontual' if entry.get('date') else 'diario',
        }

        if entry.get('date'):
            e['date'] = entry['date']

        if entry.get('replay_of') is not None:
            e['replay_of'] = entry['replay_of']
        elif entry.get('sources'):
            e['sources'] = entry['sources']

        if entry.get('slot_id') is not None:
            e['slot_id'] = entry['slot_id']

        if entry.get('days'):
            e['days'] = entry['days']

        key     = _schedule_entry_key(entry)
        run_key = f"{today}|{key}"

        if entry.get('date'):
            e['executado'] = key in completed_once
        else:
            e['executado_hoje'] = run_key in completed_today

        if (proximo_idx is None
                and not entry.get('date')
                and entry.get('time', '') >= now_time
                and run_key not in completed_today):
            e['proximo'] = True
            proximo_idx  = i

        grade.append(e)

    proximo_time = entries[proximo_idx].get('time') if proximo_idx is not None else None

    return json.dumps({
        'total_entradas':  len(grade),
        'proximo_horario': proximo_time,
        'hora_atual':      now_time,
        'grade':           grade,
        'dica':            'Use adicionar_grade() e remover_grade() para modificar a programacao.',
    }, ensure_ascii=False, indent=2)


# ── config ────────────────────────────────────────────────────────────────────

@mcp.resource("radioia://config")
def resource_config() -> str:
    """Configuracao completa do RadioIA (exceto schedule — use radioia://grade para a grade)."""
    config = _load_config()
    resumo = {k: v for k, v in config.items() if k != 'schedule'}
    resumo['schedule_entradas'] = len(config.get('schedule', []))
    return json.dumps(resumo, ensure_ascii=False, indent=2)


@mcp.resource("radioia://config/{secao}")
def resource_config_secao(secao: str) -> str:
    """Uma secao especifica do config.yaml. Secoes: sources, narrators, llm, radio, vinheta, tts, spots."""
    config = _load_config()
    if secao not in config:
        return json.dumps({
            'status':             'erro',
            'mensagem':           f"Secao '{secao}' nao encontrada.",
            'secoes_disponiveis': list(config.keys()),
        }, ensure_ascii=False, indent=2)
    return json.dumps({'secao': secao, 'conteudo': config[secao]}, ensure_ascii=False, indent=2)


# ── sistema ───────────────────────────────────────────────────────────────────

@mcp.resource("radioia://sistema")
def resource_sistema() -> str:
    """Status geral do sistema: scheduler, player, API keys, uso de disco e historico."""
    resultado = {}

    resultado['scheduler'] = _scheduler_status()

    import urllib.request
    player_ativo = False
    try:
        urllib.request.urlopen('http://localhost:5000', timeout=2)
        player_ativo = True
    except Exception:
        pass
    resultado['player'] = {
        'ativo': player_ativo,
        'url':   'http://localhost:5000',
        'dica':  'python serve.py para iniciar',
    }

    keys_check = {
        'ANTHROPIC_API_KEY':     ('obrigatorio', 'Claude API — geracao de roteiros'),
        'YOUTUBE_API_KEY':       ('obrigatorio', 'YouTube Data API — fonte youtube'),
        'OPENWEATHER_API_KEY':   ('opcional',    'Clima — fonte utilidades'),
        'FOOTBALL_DATA_API_KEY': ('opcional',    'Futebol — fontes copa/brasileirao/champions'),
        'TMDB_API_KEY':          ('opcional',    'Filmes — fontes filmes/filmes-cartaz'),
        'JAMENDO_CLIENT_ID':     ('opcional',    'Musica streaming — fonte musica'),
        'ABIBLIADIGITAL_TOKEN':  ('opcional',    'Biblia — fonte biblia'),
        'ELEVENLABS_API_KEY':    ('opcional',    'ElevenLabs TTS'),
        'OPENAI_API_KEY':        ('opcional',    'OpenAI TTS ou LLM'),
    }
    api_keys = {}
    for key, (tipo, desc) in keys_check.items():
        api_keys[key] = {
            'configurada': bool(os.environ.get(key, '')),
            'tipo':        tipo,
            'descricao':   desc,
        }
    resultado['api_keys'] = api_keys

    output_dir = os.path.join(PROJECT_DIR, 'output')
    if os.path.exists(output_dir):
        total_bytes = sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(output_dir)
            for f in files
        )
        datas_output = sorted([
            d for d in os.listdir(output_dir)
            if os.path.isdir(os.path.join(output_dir, d)) and d[:4].isdigit()
        ], reverse=True)
        resultado['output'] = {
            'tamanho_mb':     round(total_bytes / 1024 / 1024, 1),
            'dias_com_data':  len(datas_output),
            'datas_recentes': datas_output[:5],
            'dica':           'Use limpar_output(dias_manter=7) para liberar espaco.',
        }
    else:
        resultado['output'] = {'tamanho_mb': 0, 'dias_com_data': 0}

    history_path = os.path.join(PROJECT_DIR, 'history.json')
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            h = json.load(f)
        eps = h.get('episodes', [])
        resultado['historico'] = {
            'itens_vistos':    len(h.get('seen_ids', [])),
            'episodios_total': len(eps),
            'ultimo':          eps[-1]['episode_id'] if eps else None,
        }

    config = _load_config()
    resultado['radio'] = {
        'nome':          config.get('radio', {}).get('name', 'RadioIA'),
        'llm_model':     config.get('llm', {}).get('model', ''),
        'tts_provider':  config.get('tts', {}).get('provider', 'edge_tts'),
        'narradores':    [n.get('name') for n in config.get('narrators', [])],
        'fontes_ativas': [s['id'] for s in config.get('sources', []) if s.get('enabled', True)],
    }

    return json.dumps(resultado, ensure_ascii=False, indent=2)


# ── player ────────────────────────────────────────────────────────────────────

@mcp.resource("radioia://player")
def resource_player() -> str:
    """Estado atual do player web: episodios de hoje, proximo agendado e estatisticas."""
    import urllib.request

    base = 'http://localhost:5000'

    try:
        urllib.request.urlopen(f'{base}/api/episodes', timeout=3)
    except Exception:
        return json.dumps({
            'status':   'inativo',
            'mensagem': 'Player nao esta rodando. Use: python serve.py',
            'url':      base,
        }, ensure_ascii=False, indent=2)

    resultado: dict = {'status': 'ativo', 'url': base}

    try:
        with urllib.request.urlopen(f'{base}/api/episodes', timeout=3) as r:
            episodios_raw = json.loads(r.read().decode())
        hoje = datetime.now().strftime('%Y-%m-%d')
        episodios_hoje = [
            e for e in episodios_raw
            if isinstance(e, dict) and e.get('date', '') == hoje
        ]
        total_dur = sum(e.get('duration', 0) for e in episodios_hoje)
        resultado['hoje'] = {
            'total_episodios':   len(episodios_hoje),
            'duracao_total_min': round(total_dur / 60, 1),
            'episodios': [
                {
                    'id':      e.get('id', ''),
                    'nome':    e.get('source_name', ''),
                    'hora':    e.get('id', '').split('/')[-1].split('_')[0] if '/' in e.get('id', '') else '',
                    'dur_min': round(e.get('duration', 0) / 60, 1),
                }
                for e in episodios_hoje
            ],
        }
    except Exception as ex:
        resultado['hoje'] = {'erro': str(ex)}

    try:
        with urllib.request.urlopen(f'{base}/api/next-scheduled', timeout=3) as r:
            resultado['proximo_agendado'] = json.loads(r.read().decode())
    except Exception:
        resultado['proximo_agendado'] = None

    resultado['nota'] = (
        'O episodio em reproducao e controlado pelo browser (localStorage) '
        'e nao e visivel pelo servidor.'
    )

    return json.dumps(resultado, ensure_ascii=False, indent=2)


# ── log ───────────────────────────────────────────────────────────────────────

@mcp.resource("radioia://log")
def resource_log() -> str:
    """Ultimas 50 linhas do scheduler.log."""
    return _log_linhas(50)


@mcp.resource("radioia://log/{linhas}")
def resource_log_n(linhas: str) -> str:
    """Ultimas N linhas do scheduler.log. Ex: radioia://log/200"""
    try:
        n = int(linhas)
    except ValueError:
        n = 50
    return _log_linhas(n)


def _log_linhas(linhas: int) -> str:
    log_path = os.path.join(PROJECT_DIR, 'scheduler.log')

    if not os.path.exists(log_path):
        return json.dumps({
            'status':   'vazio',
            'mensagem': 'scheduler.log nao encontrado. O scheduler ainda nao foi iniciado pelo MCP.',
            'dica':     'Use controlar_scheduler("start") para iniciar.',
        }, ensure_ascii=False, indent=2)

    size_kb = round(os.path.getsize(log_path) / 1024, 1)

    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        todas = f.readlines()

    recentes = todas[-linhas:]

    return json.dumps({
        'status':            'ok',
        'arquivo':           log_path,
        'tamanho_kb':        size_kb,
        'total_linhas':      len(todas),
        'linhas_retornadas': len(recentes),
        'log':               ''.join(recentes),
    }, ensure_ascii=False, indent=2)


# ── zips WhatsApp ─────────────────────────────────────────────────────────────

@mcp.resource("radioia://zips-wp")
def resource_zips_wp() -> str:
    """Arquivos ZIP de exportacao do WhatsApp configurados no projeto."""
    config  = _load_config()
    sources = [s for s in config.get('sources', []) if s.get('type') == 'whatsapp']

    if not sources:
        return json.dumps({
            'status':   'sem_fontes',
            'mensagem': 'Nenhuma fonte do tipo whatsapp configurada no config.yaml.',
        }, ensure_ascii=False, indent=2)

    resultado = []
    for src in sources:
        path_cfg = src.get('settings', {}).get('path', '')
        entry: dict = {
            'id':               src['id'],
            'nome':             src.get('name', src['id']),
            'habilitada':       src.get('enabled', True),
            'path_configurado': path_cfg,
        }

        if not path_cfg:
            entry['status'] = 'path_nao_configurado'
            resultado.append(entry)
            continue

        if os.path.isfile(path_cfg):
            mtime   = datetime.fromtimestamp(os.path.getmtime(path_cfg)).strftime('%Y-%m-%d %H:%M')
            size_kb = round(os.path.getsize(path_cfg) / 1024, 1)
            dias    = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path_cfg))).days
            entry['status']   = 'ok'
            entry['arquivos'] = [{'nome': os.path.basename(path_cfg), 'tamanho_kb': size_kb, 'modificado': mtime, 'dias_atras': dias}]
        elif os.path.isdir(path_cfg):
            zips = sorted(
                [f for f in os.listdir(path_cfg) if f.lower().endswith('.zip')],
                key=lambda f: os.path.getmtime(os.path.join(path_cfg, f)),
                reverse=True,
            )
            if not zips:
                entry['status']   = 'pasta_vazia'
                entry['arquivos'] = []
            else:
                entry['status']   = 'ok'
                entry['arquivos'] = []
                for z in zips:
                    zp   = os.path.join(path_cfg, z)
                    mtime = datetime.fromtimestamp(os.path.getmtime(zp)).strftime('%Y-%m-%d %H:%M')
                    dias  = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(zp))).days
                    entry['arquivos'].append({
                        'nome':       z,
                        'tamanho_kb': round(os.path.getsize(zp) / 1024, 1),
                        'modificado': mtime,
                        'dias_atras': dias,
                    })
        else:
            entry['status']   = 'nao_encontrado'
            entry['arquivos'] = []

        resultado.append(entry)

    return json.dumps({'status': 'ok', 'fontes': resultado}, ensure_ascii=False, indent=2)


# ── spots ─────────────────────────────────────────────────────────────────────

@mcp.resource("radioia://spots")
def resource_spots() -> str:
    """Spots configurados: tipo, peso, limite diario e status do cache de audio."""
    config    = _load_config()
    spots     = config.get('spots') or []
    spots_cfg = config.get('spots_config', {})

    if not spots:
        return json.dumps({
            'status':   'sem_spots',
            'mensagem': 'Nenhum spot configurado em config.yaml.',
            'dica':     'Adicione spots na secao "spots:" do config.yaml.',
        }, ensure_ascii=False, indent=2)

    resultado = []
    for spot in spots:
        entry = {
            'id':          spot['id'],
            'tipo':        spot.get('type', 'file'),
            'peso':        spot.get('weight', 1),
            'max_por_dia': spot.get('max_per_day', None),
            'cache':       _spot_cache_info(spot),
        }
        if spot.get('type') == 'tts':
            entry['texto'] = spot.get('text', '')[:120]
        elif spot.get('type') == 'llm':
            entry['topico']      = spot.get('topic', '')
            entry['duracao_seg'] = spot.get('duration_seconds', 20)
            entry['modelo']      = spot.get('model', config.get('llm', {}).get('model', ''))
        elif spot.get('type') == 'file':
            entry['path'] = spot.get('path', '')
        resultado.append(entry)

    return json.dumps({
        'status':       'ok',
        'total_spots':  len(resultado),
        'spots_config': spots_cfg,
        'spots':        resultado,
        'cache_dir':    _SPOTS_CACHE_DIR,
    }, ensure_ascii=False, indent=2)


# ── jamendo ───────────────────────────────────────────────────────────────────

@mcp.resource("radioia://jamendo")
def resource_jamendo() -> str:
    """Cache local do Jamendo: faixas catalogadas, tamanho em disco e fontes configuradas."""
    from src.sources.music import CACHE_DIR, CATALOG_FILE

    config = _load_config()
    jamendo_sources = [
        s for s in config.get('sources', [])
        if s.get('type') == 'music'
        and (s.get('settings') or {}).get('source') == 'jamendo'
    ]

    catalog = {}
    if os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

    total_bytes     = 0
    faixas_ok       = 0
    faixas_faltando = []
    for tid, meta in catalog.items():
        fpath = os.path.join(CACHE_DIR, meta['file'])
        if os.path.exists(fpath):
            total_bytes += os.path.getsize(fpath)
            faixas_ok   += 1
        else:
            faixas_faltando.append(meta.get('title', tid))

    amostra = [
        {'titulo': m['title'], 'artista': m['artist']}
        for m in list(catalog.values())[:5]
    ]

    return json.dumps({
        'faixas_em_catalogo':  len(catalog),
        'faixas_no_disco':     faixas_ok,
        'faixas_faltando':     len(faixas_faltando),
        'tamanho_mb':          round(total_bytes / 1024 / 1024, 1),
        'fontes_configuradas': [
            {
                'id':         s['id'],
                'name':       s.get('name', s['id']),
                'enabled':    s.get('enabled', True),
                'tags':       (s.get('settings') or {}).get('jamendo', {}).get('tags', 'lounge'),
                'cache_size': (s.get('settings') or {}).get('cache_size', 50),
            }
            for s in jamendo_sources
        ],
        'amostra': amostra,
    }, ensure_ascii=False, indent=2)


# ── intro boas-vindas ─────────────────────────────────────────────────────────

@mcp.resource("radioia://intro")
def resource_intro() -> str:
    """Configuracao da intro de boas-vindas e status do audio gerado."""
    config = _load_config()
    wi     = config.get('welcome_intro', {})
    exists = os.path.exists(_WELCOME_INTRO_PATH)
    result = {
        'falas':        wi.get('falas', []),
        'voice':        wi.get('voice'),
        'audio_gerado': exists,
    }
    if exists:
        mtime = datetime.fromtimestamp(os.path.getmtime(_WELCOME_INTRO_PATH)).strftime('%Y-%m-%d %H:%M')
        result['gerado_em']  = mtime
        result['tamanho_kb'] = round(os.path.getsize(_WELCOME_INTRO_PATH) / 1024, 1)
    return json.dumps(result, ensure_ascii=False, indent=2)
