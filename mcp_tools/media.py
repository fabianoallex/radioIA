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
