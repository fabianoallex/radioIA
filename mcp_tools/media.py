import json
import os
from datetime import datetime

import main as radio_main
from src.history import load_seen_ids

from mcp_tools._instance import mcp
from mcp_tools._utils import PROJECT_DIR, _load_config, _save_config, _capture

_WELCOME_INTRO_PATH = os.path.join(PROJECT_DIR, 'output', '_welcome_intro.mp3')


# ── Clipping ──────────────────────────────────────────────────────────────────

@mcp.tool()
def gerar_clipping(topico: str, followup: bool = False, model: str = '',
                   agregadores: list = None) -> str:
    """
    Gera um episodio de clipping — panorama de como a midia esta cobrindo um tema.
    Busca em multiplos agregadores de noticias, seleciona veiculos de forma balanceada
    (round-robin) e narra as convergencias e divergencias entre eles.

    Nao requer configuracao previa no config.yaml.

    Args:
        topico:      Tema a pesquisar. Pode ser qualquer assunto atual. Exemplos:
                     "queda de aviao da empresa xyz"
                     "reforma tributaria 2026"
                     "copa do mundo abertura"
                     "novo iphone lancamento"
        followup:    Se True, busca apenas artigos mais recentes sobre o tema
                     (util para acompanhar um assunto que ja foi clippado antes).
                     Default: False.
        model:       Modelo LLM para esta geracao (ex: "claude-haiku-4-5-20251001").
                     Sobrescreve o modelo configurado em llm.model apenas para esta chamada.
                     Se vazio, usa o modelo padrao do config.
        agregadores: Lista de agregadores a usar nesta chamada. Sobrescreve o valor do
                     config.yaml apenas para esta execucao. Opcoes disponiveis:
                     ["google_news", "bing_news"]
                     Se omitido, usa o configurado em clipping.settings.agregadores
                     (padrao: ambos).

    Para descoberta automática do assunto do dia use gerar_clipping_automatico().

    Equivalente CLI: python main.py "clipping:tema"  (ou com --followup)
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

    base = next((s for s in all_sources if s['id'] == 'clipping'), {})
    extra_settings = {'topic': topico, 'followup': followup}
    if agregadores is not None:
        extra_settings['agregadores'] = list(agregadores)
    source_cfg = {
        **base,
        'id':      'clipping',
        'type':    'clipping',
        'name':    f"Clipping — {topico[:60]}",
        'enabled': True,
        'settings': {**(base.get('settings') or {}), **extra_settings},
    }

    if model:
        source_cfg = {**source_cfg, 'model': model}

    path, log, err = _capture(
        radio_main._run_source, source_cfg, config, credentials, seen_ids, first_of_day
    )

    if path and os.path.exists(path):
        meta_path = os.path.join(os.path.dirname(path), 'episode.json')
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        dur = meta.get('duration_seconds', 0)
        return json.dumps({
            'status':   'ok',
            'topico':   topico,
            'followup': followup,
            'nome':     meta.get('source_name', source_cfg['name']),
            'duracao':  f"{dur // 60}m {dur % 60}s",
            'itens':    meta.get('videos_covered', 0),
            'arquivo':  path,
            'log':      log.strip(),
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':   'erro',
        'topico':   topico,
        'mensagem': err or 'Nenhum episodio gerado. Verifique se ha artigos recentes sobre o tema.',
        'log':      log.strip(),
    }, ensure_ascii=False, indent=2)


# ── Clipping Automático ───────────────────────────────────────────────────────

@mcp.tool()
def gerar_clipping_automatico(
    categoria: str = '',
    topic_history_days: int = 7,
    topic_cooldown_hours: int = 4,
    max_sources: int = 5,
    model: str = '',
) -> str:
    """
    Gera um episodio de clipping descobrindo automaticamente o assunto mais discutido
    do dia. Consulta RSS de grandes portais brasileiros, usa o LLM para identificar o
    topico e gera o clipping normalmente sobre ele.

    Tres mecanismos evitam repeticao:
    - topic_history_days: nao repete topicos dos ultimos N dias
    - topic_cooldown_hours: nao repete o mesmo assunto nas ultimas N horas (intra-dia)
    - followup automatico: se o topico ja foi coberto hoje, usa modo de acompanhamento

    Args:
        categoria:            Tema para filtrar o LLM: "politica", "economia", "esportes",
                              "tecnologia", "saude", "cultura" etc.
                              Se vazio, cobre qualquer assunto em destaque.
        topic_history_days:   Janela de exclusao inter-dia (default: 7).
        topic_cooldown_hours: Janela de exclusao intra-dia em horas (default: 4).
        max_sources:          Maximo de veiculos no clipping (default: 5).
        model:                Modelo LLM para o roteiro. Vazio = usa padrao do config.

    Exemplos:
        gerar_clipping_automatico()
        gerar_clipping_automatico(categoria="economia")
        gerar_clipping_automatico(categoria="esportes", topic_history_days=3)

    Para clipping com topico especifico use gerar_clipping("tema").
    Equivalente CLI: python main.py clipping-auto
    """
    config       = _load_config()
    all_sources  = config.get('sources', [])
    seen_ids     = load_seen_ids()
    credentials  = radio_main._get_oauth_credentials()
    first_of_day = not radio_main._has_episodes_today()

    if model:
        modelos_cfg = config.get('llm', {}).get('modelos', [])
        if modelos_cfg:
            ids_permitidos = [m['id'] for m in modelos_cfg]
            if model not in ids_permitidos:
                return json.dumps({
                    'status':            'erro',
                    'mensagem':          f"Modelo '{model}' nao esta na lista de modelos permitidos.",
                    'modelos_permitidos': modelos_cfg,
                    'dica':              'Use listar_modelos() para ver as opcoes disponiveis.',
                }, ensure_ascii=False, indent=2)

    base         = next((s for s in all_sources if s['id'] == 'clipping-auto'), {})
    base_settings = base.get('settings') or {}

    settings = {
        **base_settings,
        'max_sources':          max_sources,
        'topic_history_days':   topic_history_days,
        'topic_cooldown_hours': topic_cooldown_hours,
    }
    if categoria:
        settings['categoria'] = categoria

    source_cfg = {
        **base,
        'id':      'clipping-auto',
        'type':    'clipping_auto',
        'name':    f"Clipping{' ' + categoria.title() if categoria else ''} do Dia",
        'enabled': True,
        'settings': settings,
    }
    if model:
        source_cfg = {**source_cfg, 'model': model}

    path, log, err = _capture(
        radio_main._run_source, source_cfg, config, credentials, seen_ids, first_of_day
    )

    if path and os.path.exists(path):
        meta_path = os.path.join(os.path.dirname(path), 'episode.json')
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        dur = meta.get('duration_seconds', 0)
        return json.dumps({
            'status':    'ok',
            'categoria': categoria or 'geral',
            'episodio':  meta.get('source_name', source_cfg['name']),
            'duracao':   f"{dur // 60}m {dur % 60}s",
            'itens':     meta.get('videos_covered', 0),
            'arquivo':   path,
            'log':       log.strip(),
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':    'erro',
        'categoria': categoria or 'geral',
        'mensagem':  err or 'Nenhum episodio gerado. Verifique se ha manchetes disponiveis.',
        'log':       log.strip(),
    }, ensure_ascii=False, indent=2)


# ── Podcast ───────────────────────────────────────────────────────────────────

@mcp.tool()
def gerar_podcast(
    url: str,
    nome: str = '',
    start: int = 0,
    duration: int = 600,
    topic: str = '',
    whisper_model: str = 'base',
    show_notes_min_chars: int = 500,
) -> str:
    """
    Gera um episodio de radio a partir de um podcast (RSS feed ou URL direta de MP3).
    Usa show notes do RSS quando suficientes; caso contrario, transcreve um trecho com Whisper.

    Nao requer configuracao previa no config.yaml.

    Args:
        url:                  URL do RSS feed do podcast OU URL direta do arquivo MP3.
        nome:                 Nome do segmento na programacao (ex: "Hipsters Podcast").
                              Se vazio, usa o titulo do feed RSS ou o nome do arquivo.
        start:                Inicio do trecho a transcrever, em segundos (default: 0).
                              Util para pular intro/patrocinadores.
        duration:             Duracao do trecho a transcrever, em segundos (default: 600 = 10min).
        topic:                Tema especifico para focar no roteiro. Se informado,
                              o narrador se concentra nesse assunto dentro do episodio.
        whisper_model:        Tamanho do modelo Whisper: tiny/base/small/medium/large.
                              Modelos maiores sao mais precisos mas mais lentos.
        show_notes_min_chars: Minimo de caracteres nas show notes para nao usar Whisper.
                              Default: 500.

    Exemplos:
        gerar_podcast("https://feeds.feedburner.com/hipsters-ponto-tech")
        gerar_podcast("https://feeds.example.com/podcast.rss", topic="inteligencia artificial")
        gerar_podcast("https://media.example.com/ep42.mp3", nome="Lex Fridman", start=120, duration=900)
    """
    config      = _load_config()
    all_sources = config.get('sources', [])
    seen_ids    = load_seen_ids()
    credentials = radio_main._get_oauth_credentials()
    first_of_day = not radio_main._has_episodes_today()

    base = next((s for s in all_sources if s.get('type') == 'podcast'), {})
    source_cfg = {
        **base,
        'id':      'podcast',
        'type':    'podcast',
        'name':    nome or base.get('name', 'Podcast'),
        'enabled': True,
        'settings': {
            **(base.get('settings') or {}),
            'url':                  url,
            'whisper_start':        start,
            'whisper_duration':     duration,
            'whisper_model':        whisper_model,
            'show_notes_min_chars': show_notes_min_chars,
            **({'topic': topic} if topic else {}),
        },
    }

    path, log, err = _capture(
        radio_main._run_source, source_cfg, config, credentials, seen_ids, first_of_day
    )

    if path and os.path.exists(path):
        meta_path = os.path.join(os.path.dirname(path), 'episode.json')
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        dur = meta.get('duration_seconds', 0)
        return json.dumps({
            'status':   'ok',
            'url':      url,
            'nome':     meta.get('source_name', source_cfg['name']),
            'topic':    topic or None,
            'trecho':   f"{start // 60}-{(start + duration) // 60} min" if start else f"primeiros {duration // 60} min",
            'duracao':  f"{dur // 60}m {dur % 60}s",
            'itens':    meta.get('videos_covered', 0),
            'arquivo':  path,
            'log':      log.strip(),
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':   'erro',
        'url':      url,
        'mensagem': err or 'Nenhum episodio gerado. Verifique se a URL e acessivel e se o Whisper esta instalado (pip install openai-whisper) caso as show notes sejam insuficientes.',
        'log':      log.strip(),
    }, ensure_ascii=False, indent=2)


# ── Intro de boas-vindas ──────────────────────────────────────────────────────

def _gerar_audio_welcome(config: dict) -> dict:
    import asyncio
    import random
    import edge_tts

    wi         = config.get('welcome_intro', {})
    falas      = wi.get('falas') or []
    radio_name = config.get('radio', {}).get('name', 'RadioIA')
    voice      = wi.get('voice') or config.get('vinheta', {}).get('voice', 'pt-BR-FranciscaNeural')

    if not falas:
        return {'status': 'erro', 'mensagem': 'Nenhuma fala configurada em welcome_intro.falas.'}

    fala = random.choice(falas).replace('{radio_name}', radio_name)
    os.makedirs(os.path.join(PROJECT_DIR, 'output'), exist_ok=True)

    async def _synth():
        await edge_tts.Communicate(fala, voice).save(_WELCOME_INTRO_PATH)

    try:
        asyncio.run(_synth())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_synth())
        loop.close()

    if not os.path.exists(_WELCOME_INTRO_PATH):
        return {'status': 'erro', 'mensagem': 'Arquivo não gerado.'}

    return {
        'status':     'ok',
        'fala_usada': fala,
        'voice':      voice,
        'arquivo':    _WELCOME_INTRO_PATH,
        'tamanho_kb': round(os.path.getsize(_WELCOME_INTRO_PATH) / 1024, 1),
    }


@mcp.tool()
def configurar_intro_boas_vindas(
    falas: list = None,
    voice: str = None,
    regenerar: bool = True,
) -> str:
    """
    Configura as frases e/ou a voz da intro de boas-vindas e opcionalmente regera o áudio.

    Parâmetros:
    - falas: lista de frases; uma é sorteada a cada geração.
             Use {radio_name} para inserir o nome da rádio. Exemplos:
             ["Bom dia! Bem-vindo à {radio_name}. Aproveite a programação!"]
             ["Olá! Você está na {radio_name}.", "Bom dia! A {radio_name} começa agora!"]
    - voice: voz edge-tts (ex: "pt-BR-FranciscaNeural"). null = herda vinheta.voice
    - regenerar: se True (padrão), apaga o áudio atual e regera imediatamente

    Pelo menos um dos parâmetros falas ou voice deve ser informado.
    """
    if falas is None and voice is None:
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Informe ao menos falas ou voice.',
        }, ensure_ascii=False)

    config = _load_config()
    if 'welcome_intro' not in config:
        config['welcome_intro'] = {}

    anterior = dict(config['welcome_intro'])

    if falas is not None:
        config['welcome_intro']['falas'] = list(falas)
    if voice is not None:
        config['welcome_intro']['voice'] = voice or None

    _save_config(config)

    result = {
        'status':         'ok',
        'valor_anterior': anterior,
        'valor_novo':     config['welcome_intro'],
        'aviso':          'config.yaml foi reformatado — comentários originais foram perdidos.',
    }

    if regenerar:
        if os.path.exists(_WELCOME_INTRO_PATH):
            os.remove(_WELCOME_INTRO_PATH)
        result['geracao'] = _gerar_audio_welcome(config)

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def regenerar_intro_boas_vindas() -> str:
    """
    Apaga o áudio atual da intro de boas-vindas e gera um novo com a configuração atual.
    Use após editar manualmente config.yaml ou para sortear uma fala diferente da lista.
    """
    config = _load_config()
    wi = config.get('welcome_intro', {})
    if not wi.get('falas'):
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Nenhuma fala configurada em welcome_intro.falas.',
            'dica':     'Use configurar_intro_boas_vindas(falas=[...]) para definir as frases.',
        }, ensure_ascii=False)

    if os.path.exists(_WELCOME_INTRO_PATH):
        os.remove(_WELCOME_INTRO_PATH)

    return json.dumps(_gerar_audio_welcome(config), ensure_ascii=False, indent=2)


# ── Cache Jamendo ─────────────────────────────────────────────────────────────

@mcp.tool()
def baixar_musicas_jamendo(id_fonte: str = None) -> str:
    """
    Baixa novas faixas do Jamendo para o cache local.

    Parâmetros:
    - id_fonte: ID da fonte music/jamendo a baixar. Omita para baixar de todas as
                fontes Jamendo configuradas.

    Requer JAMENDO_CLIENT_ID definido no .env.
    Faixas já presentes no cache são ignoradas (não rebaixadas).
    """
    from src.sources import music as music_source

    config = _load_config()
    jamendo_sources = [
        s for s in config.get('sources', [])
        if s.get('type') == 'music'
        and (s.get('settings') or {}).get('source') == 'jamendo'
    ]

    if not jamendo_sources:
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Nenhuma fonte do tipo music/jamendo configurada.',
            'dica':     'Adicione uma fonte com type: music e settings.source: jamendo no config.yaml.',
        }, ensure_ascii=False, indent=2)

    if id_fonte:
        fontes = [s for s in jamendo_sources if s['id'] == id_fonte]
        if not fontes:
            return json.dumps({
                'status':      'erro',
                'mensagem':    f"Fonte '{id_fonte}' não encontrada entre as fontes Jamendo.",
                'disponiveis': [s['id'] for s in jamendo_sources],
            }, ensure_ascii=False, indent=2)
    else:
        fontes = jamendo_sources

    resultados = []
    for src in fontes:
        n = music_source.download_cache(src)
        resultados.append({
            'id':           src['id'],
            'name':         src.get('name', src['id']),
            'novas_faixas': n,
        })

    return json.dumps({
        'status':      'ok',
        'total_novas': sum(r['novas_faixas'] for r in resultados),
        'por_fonte':   resultados,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def limpar_cache_jamendo(confirmar: bool = False) -> str:
    """
    Apaga todos os arquivos de áudio e o catálogo do cache local do Jamendo.

    Parâmetros:
    - confirmar: deve ser True para executar (proteção contra apagamento acidental).
                 Chame primeiro sem confirmar para ver o que seria removido.

    Use baixar_musicas_jamendo() para repopular o cache após limpar.
    """
    from src.sources.music import CACHE_DIR

    n_files     = 0
    total_bytes = 0
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            fpath = os.path.join(CACHE_DIR, f)
            if os.path.isfile(fpath):
                n_files     += 1
                total_bytes += os.path.getsize(fpath)

    if not confirmar:
        return json.dumps({
            'status':   'aguardando_confirmacao',
            'mensagem': f'Isso removerá {n_files} arquivo(s) ({round(total_bytes/1024/1024, 1)} MB). '
                        f'Chame novamente com confirmar=True para executar.',
        }, ensure_ascii=False, indent=2)

    removidos = 0
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            fpath = os.path.join(CACHE_DIR, f)
            if os.path.isfile(fpath):
                os.remove(fpath)
                removidos += 1

    return json.dumps({
        'status':             'ok',
        'arquivos_removidos': removidos,
        'espaco_liberado_mb': round(total_bytes / 1024 / 1024, 1),
    }, ensure_ascii=False, indent=2)


# ── Enriquecimento de metadados ───────────────────────────────────────────────

@mcp.tool()
def enriquecer_musicas(
    paths: list = None,
    todos: bool = False,
    write_back: bool = True,
    min_score: int = 80,
) -> str:
    """
    Busca metadados de músicas locais no MusicBrainz e atualiza as tags ID3/FLAC/M4A/OGG.
    Antes de sobrescrever qualquer dado, salva os valores originais (incluindo capa APIC)
    em music/metadata_backup.json para restore posterior.

    Parâmetros:
    - paths:      Lista de caminhos absolutos a enriquecer. Se omitido com todos=True,
                  processa músicas sem artista ou álbum.
    - todos:      Se True e paths não informado, varre toda a biblioteca local.
                  Default: False (proteção contra alteração em massa acidental).
    - write_back: Se False, apenas retorna o que seria gravado sem modificar arquivos.
                  Default: True.
    - min_score:  Score mínimo de confiança MusicBrainz (0–100). Default: 80.

    Rate limit: respeita 1 req/s para o MusicBrainz (termos de uso).
    Use restaurar_metadados_musica() para desfazer. Use listar_backup_musicas() para ver
    o que está no backup.
    """
    import time
    from src.sources.music_enricher import enrich_file, _read_current_tags
    from mcp_tools._utils import PROJECT_DIR

    audio_exts = {'.mp3', '.m4a', '.ogg', '.wav', '.flac'}
    music_dir  = os.path.join(PROJECT_DIR, 'music')

    if paths:
        targets     = []
        path_issues = []
        for p in paths:
            ap = os.path.abspath(p)
            if os.path.isfile(ap):
                targets.append(ap)
            elif os.path.isdir(ap):
                before = len(targets)
                for dirpath, _, filenames in os.walk(ap):
                    for f in filenames:
                        if os.path.splitext(f)[1].lower() in audio_exts:
                            targets.append(os.path.join(dirpath, f))
                if len(targets) == before:
                    path_issues.append(f'diretório sem áudio: {ap}')
            else:
                path_issues.append(f'não encontrado (arquivo nem diretório): {ap}')
    elif todos:
        targets = []
        jamendo_cache = os.path.abspath(os.path.join(music_dir, 'cache', 'jamendo'))
        if os.path.isdir(music_dir):
            for dirpath, _, filenames in os.walk(music_dir):
                if os.path.abspath(dirpath).startswith(jamendo_cache):
                    continue
                for f in filenames:
                    if os.path.splitext(f)[1].lower() in audio_exts:
                        targets.append(os.path.join(dirpath, f))
        config = _load_config()
        for src in config.get('sources', []):
            if src.get('type') == 'music' and (src.get('settings') or {}).get('source') == 'local':
                for extra in (src['settings'].get('paths') or []):
                    if os.path.isdir(extra):
                        for dirpath, _, filenames in os.walk(extra):
                            for f in filenames:
                                if os.path.splitext(f)[1].lower() in audio_exts:
                                    targets.append(os.path.join(dirpath, f))
        # Filtra arquivos sem metadados completos OU sem capa embutida
        incomplete = []
        for p in targets:
            info = _read_current_tags(p)
            if not info['artist'] or not info['album'] or not info['apic']:
                incomplete.append(p)
        targets = incomplete
    else:
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Informe paths ou use todos=True para processar toda a biblioteca.',
        }, ensure_ascii=False, indent=2)

    if not targets:
        resp = {'status': 'ok', 'mensagem': 'Nenhum arquivo para processar.'}
        if paths and path_issues:
            resp['paths_problematicos'] = path_issues
        return json.dumps(resp, ensure_ascii=False, indent=2)

    results = {'ok': [], 'no_match': [], 'error': []}
    for i, path in enumerate(targets):
        if i > 0:
            time.sleep(1)   # Rate limit MusicBrainz
        r   = enrich_file(path, write_back=write_back, min_score=min_score)
        key = r.get('status', 'error')
        if key == 'found':   # write_back=False com match → conta como ok
            key = 'ok'
        if key not in results:
            key = 'error'
        results[key].append({
            'path':  path,
            'match': r.get('match'),
            'cover': r.get('has_cover', False),
            'msg':   r.get('message', ''),
        })

    return json.dumps({
        'status':       'ok',
        'total':        len(targets),
        'enriquecidos': len(results['ok']),
        'sem_match':    len(results['no_match']),
        'erros':        len(results['error']),
        'write_back':   write_back,
        'detalhes':     results,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def restaurar_metadados_musica(path: str = '', todos: bool = False) -> str:
    """
    Restaura os metadados originais (título, artista, álbum e capa APIC) de uma música
    a partir do backup gerado pelo enriquecer_musicas(). Remove a entrada do backup após
    restaurar com sucesso.

    Parâmetros:
    - path:  Caminho absoluto do arquivo a restaurar. Obrigatório se todos=False.
    - todos: Se True, restaura todos os arquivos presentes no backup. Default: False.
    """
    from src.sources.music_enricher import restore_file, list_backup

    if todos:
        entries = list_backup()
        if not entries:
            return json.dumps({
                'status':   'ok',
                'mensagem': 'Nenhum backup encontrado para restaurar.',
            }, ensure_ascii=False, indent=2)
        results = [restore_file(e['path']) for e in entries]
        ok      = [r for r in results if r['status'] == 'ok']
        erros   = [r for r in results if r['status'] != 'ok']
        return json.dumps({
            'status':      'ok',
            'restaurados': len(ok),
            'erros':       len(erros),
            'detalhes':    results,
        }, ensure_ascii=False, indent=2)

    if not path:
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Informe path ou use todos=True.',
        }, ensure_ascii=False, indent=2)

    return json.dumps(restore_file(os.path.abspath(path)), ensure_ascii=False, indent=2)


@mcp.tool()
def listar_backup_musicas() -> str:
    """
    Lista todos os arquivos de música com backup de metadados disponível para restore.
    Mostra os valores originais (antes do enriquecimento), incluindo se havia capa APIC.
    """
    from src.sources.music_enricher import list_backup
    entries = list_backup()
    if not entries:
        return json.dumps({
            'status':   'ok',
            'mensagem': 'Nenhum backup encontrado.',
            'backup':   [],
        }, ensure_ascii=False, indent=2)
    return json.dumps({
        'status': 'ok',
        'total':  len(entries),
        'backup': entries,
    }, ensure_ascii=False, indent=2)


# ── Renomeação de arquivos ────────────────────────────────────────────────────

@mcp.tool()
def renomear_musicas(
    paths: list = None,
    todos: bool = False,
    padrao: str = 'artist_title',
    dry_run: bool = True,
) -> str:
    """
    Renomeia arquivos de música com base nas tags ID3/FLAC/M4A existentes.
    Executa em modo simulação por padrão — use dry_run=False para aplicar.

    Padrões disponíveis:
    - "artist_title":       "Artista - Título.mp3"         (padrão)
    - "artist_album_title": "Artista - Álbum - Título.mp3"

    Parâmetros:
    - paths:   Lista de caminhos absolutos a renomear. Se omitido, requer todos=True.
    - todos:   Se True, processa toda a biblioteca local (exclui cache Jamendo).
    - padrao:  Padrão de nomenclatura. Default: "artist_title".
    - dry_run: Se True (padrão), simula sem renomear — mostra old_name → new_name.
               Passe dry_run=False para aplicar as renomeações.

    O nome original é salvo em music/metadata_backup.json antes de renomear.
    Use restaurar_nomes_musicas() para desfazer e listar_renomes_musicas() para ver
    o que está no backup.

    Dica: rode enriquecer_musicas() antes para garantir que as tags estão corretas.
    """
    from src.sources.music_enricher import rename_file
    from mcp_tools._utils import PROJECT_DIR

    audio_exts = {'.mp3', '.m4a', '.ogg', '.wav', '.flac'}
    music_dir  = os.path.join(PROJECT_DIR, 'music')

    if paths:
        targets = []
        for p in paths:
            ap = os.path.abspath(p)
            if os.path.isfile(ap):
                targets.append(ap)
            elif os.path.isdir(ap):
                for dirpath, _, filenames in os.walk(ap):
                    for f in filenames:
                        if os.path.splitext(f)[1].lower() in audio_exts:
                            targets.append(os.path.join(dirpath, f))
    elif todos:
        targets       = []
        jamendo_cache = os.path.abspath(os.path.join(music_dir, 'cache', 'jamendo'))
        if os.path.isdir(music_dir):
            for dirpath, _, filenames in os.walk(music_dir):
                if os.path.abspath(dirpath).startswith(jamendo_cache):
                    continue
                for f in filenames:
                    if os.path.splitext(f)[1].lower() in audio_exts:
                        targets.append(os.path.join(dirpath, f))
        config = _load_config()
        for src in config.get('sources', []):
            if src.get('type') == 'music' and (src.get('settings') or {}).get('source') == 'local':
                for extra in (src['settings'].get('paths') or []):
                    if os.path.isdir(extra):
                        for dirpath, _, filenames in os.walk(extra):
                            for f in filenames:
                                if os.path.splitext(f)[1].lower() in audio_exts:
                                    targets.append(os.path.join(dirpath, f))
    else:
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Informe paths ou use todos=True.',
        }, ensure_ascii=False, indent=2)

    if not targets:
        return json.dumps({
            'status':   'ok',
            'mensagem': 'Nenhum arquivo encontrado.',
        }, ensure_ascii=False, indent=2)

    buckets = {'ok': [], 'unchanged': [], 'skip': [], 'collision': [], 'error': []}
    for path in targets:
        r   = rename_file(path, pattern=padrao, dry_run=dry_run)
        key = r.get('status', 'error')
        if key == 'dry_run':
            key = 'ok'
        if key not in buckets:
            key = 'error'
        buckets[key].append(r)

    return json.dumps({
        'status':      'simulacao' if dry_run else 'ok',
        'dry_run':     dry_run,
        'padrao':      padrao,
        'total':       len(targets),
        'renomeados':  len(buckets['ok']),
        'sem_mudanca': len(buckets['unchanged']),
        'sem_titulo':  len(buckets['skip']),
        'colisoes':    len(buckets['collision']),
        'erros':       len(buckets['error']),
        'detalhes':    buckets,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def restaurar_nomes_musicas(path: str = '', todos: bool = False) -> str:
    """
    Restaura os nomes originais de arquivos renomeados pelo renomear_musicas().
    Remove a entrada do backup após restaurar com sucesso.

    Parâmetros:
    - path:  Caminho atual (pós-rename) do arquivo a restaurar. Requerido se todos=False.
    - todos: Se True, restaura todos os arquivos com rename no backup.
    """
    from src.sources.music_enricher import restore_rename, list_renames

    if todos:
        entries = list_renames()
        if not entries:
            return json.dumps({
                'status':   'ok',
                'mensagem': 'Nenhum rename registrado no backup.',
            }, ensure_ascii=False, indent=2)
        results = [restore_rename(e['current_path']) for e in entries]
        ok      = [r for r in results if r['status'] == 'ok']
        erros   = [r for r in results if r['status'] != 'ok']
        return json.dumps({
            'status':      'ok',
            'restaurados': len(ok),
            'erros':       len(erros),
            'detalhes':    results,
        }, ensure_ascii=False, indent=2)

    if not path:
        return json.dumps({
            'status':   'erro',
            'mensagem': 'Informe path ou use todos=True.',
        }, ensure_ascii=False, indent=2)

    return json.dumps(
        restore_rename(os.path.abspath(path)),
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
def listar_renomes_musicas() -> str:
    """
    Lista todos os arquivos que tiveram o nome alterado por renomear_musicas(),
    mostrando o nome atual e o original disponível para restore.
    """
    from src.sources.music_enricher import list_renames
    entries = list_renames()
    if not entries:
        return json.dumps({
            'status':   'ok',
            'mensagem': 'Nenhum rename registrado no backup.',
            'renomes':  [],
        }, ensure_ascii=False, indent=2)
    return json.dumps({
        'status':  'ok',
        'total':   len(entries),
        'renomes': entries,
    }, ensure_ascii=False, indent=2)
