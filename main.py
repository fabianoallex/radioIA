import json
import os
import sys
import shutil

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import importlib.util
import yaml
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.sources import youtube, rss, music as music_source, utility as utility_source
from src.script_generator import generate_script
from src.tts_generator import parse_script, generate_audio_files
from src.audio_mixer import mix_episode, save_episode_metadata
from src.vinheta import generate_vinhetas
from src.history import load_seen_ids, save_episode_to_history

load_dotenv(override=True)

_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geracao_status.json')

# ── Log de geração ────────────────────────────────────────────────────────────

class _Tee:
    def __init__(self, *streams):
        self._streams = streams
    def write(self, data):
        for s in self._streams:
            try: s.write(data)
            except Exception: pass
    def flush(self):
        for s in self._streams:
            try: s.flush()
            except Exception: pass

_log_file = None
_log_orig = None


def _begin_log(output_dir: str):
    global _log_file, _log_orig
    _end_log()
    os.makedirs(output_dir, exist_ok=True)
    try:
        _log_file = open(os.path.join(output_dir, 'generation.log'), 'w', encoding='utf-8', buffering=1)
        _log_orig = sys.stdout
        sys.stdout = _Tee(_log_orig, _log_file)
    except Exception:
        pass


def _end_log():
    global _log_file, _log_orig
    if _log_orig is not None:
        sys.stdout = _log_orig
        _log_orig = None
    if _log_file is not None:
        try: _log_file.close()
        except Exception: pass
        _log_file = None


import atexit as _atexit
_atexit.register(_end_log)

# ─────────────────────────────────────────────────────────────────────────────


def _write_status(source_id: str, source_name: str, etapa: str,
                  progresso: str = '', inicio: str = '', ativo: bool = True,
                  erro: str = None, publicar: bool = True):
    try:
        with open(_STATUS_FILE, 'w', encoding='utf-8') as _f:
            json.dump({
                'ativo':      ativo,
                'fonte':      source_id,
                'fonte_nome': source_name,
                'etapa':      etapa,
                'progresso':  progresso,
                'inicio':     inicio,
                'data':       _local_now().strftime('%Y-%m-%d'),
                'atualizado': _local_now().strftime('%H:%M:%S'),
                'erro':       erro,
                'publicar':   publicar,
            }, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_plugins() -> dict:
    """Carrega dinamicamente os módulos de src/sources/plugins/."""
    plugins_dir = 'plugins'
    modules = {}
    if not os.path.isdir(plugins_dir):
        return modules
    for filename in sorted(os.listdir(plugins_dir)):
        if not filename.endswith('.py') or filename.startswith('_'):
            continue
        name = filename[:-3]
        try:
            spec   = importlib.util.spec_from_file_location(f'plugins.{name}',
                                                             os.path.join(plugins_dir, filename))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'fetch'):
                modules[name] = module
                print(f"  Plugin carregado: {name}")
            else:
                print(f"  [plugin/{name}] ignorado — sem função fetch()")
        except Exception as e:
            print(f"  [plugin/{name}] erro ao carregar: {e}")
    return modules


SOURCE_MODULES = {
    'youtube': youtube,
    'rss':     rss,
    'music':   music_source,
    'utility': utility_source,
}

SOURCE_MODULES.update(_load_plugins())


def load_config(path: str = 'config.yaml') -> dict:
    from src.config_schema import validate_config, ConfigError
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    try:
        validate_config(raw)
    except ConfigError as e:
        print(e)
        sys.exit(1)
    return raw


def _get_oauth_credentials():
    try:
        from src.auth import get_youtube_credentials
        return get_youtube_credentials()
    except Exception as e:
        print(f"  [aviso OAuth] {type(e).__name__}: {e}")
        return None


def _local_now() -> datetime:
    """Retorna datetime atual no fuso configurado em radio.utc_offset do config.yaml."""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as _f:
            _cfg = yaml.safe_load(_f) or {}
        offset = int((_cfg.get('radio') or {}).get('utc_offset', 0))
    except Exception:
        offset = 0
    return datetime.utcnow() + timedelta(hours=offset)


def _has_episodes_today() -> bool:
    today   = _local_now().strftime('%Y-%m-%d')
    day_dir = os.path.join('output', today)
    if not os.path.exists(day_dir):
        return False
    return any(
        os.path.exists(os.path.join(day_dir, f, 'episode.mp3'))
        for f in os.listdir(day_dir)
        if os.path.isdir(os.path.join(day_dir, f))
    )


def _episode_output_dir(source_id: str) -> str:
    now = _local_now()
    return os.path.join('output', now.strftime('%Y-%m-%d'), now.strftime('%H-%M') + f'_{source_id}')


def _run_replay_cli(partial: str, today: str | None = None) -> list[str]:
    """Cria replays dos episódios cujas pastas batem com o prefixo parcial.

    Retorna lista de caminhos para os episode.json criados.
    """
    import json as _json
    if not today:
        today = _local_now().strftime('%Y-%m-%d')

    day_dir = os.path.join('output', today)
    if not os.path.isdir(day_dir):
        print(f"  Nenhum episodio encontrado para {today}.")
        return []

    matches = sorted([
        f for f in os.listdir(day_dir)
        if f.startswith(partial)
        and os.path.isdir(os.path.join(day_dir, f))
        and os.path.exists(os.path.join(day_dir, f, 'episode.mp3'))
    ])

    if not matches:
        print(f"  Nenhum episodio com prefixo '{partial}' em {today}.")
        available = sorted([
            f for f in os.listdir(day_dir)
            if os.path.isdir(os.path.join(day_dir, f))
        ])
        if available:
            print(f"  Disponiveis: {', '.join(available)}")
        return []

    now = _local_now().strftime('%H-%M')
    created = []

    for folder in matches:
        orig_dir  = os.path.join(day_dir, folder)
        orig_mp3  = os.path.join(orig_dir, 'episode.mp3')
        orig_json = os.path.join(orig_dir, 'episode.json')

        source_id  = folder.split('_', 1)[1] if '_' in folder else folder
        output_dir = os.path.join(day_dir, f"{now}_{source_id}")

        os.makedirs(output_dir, exist_ok=True)

        meta = {}
        if os.path.exists(orig_json):
            with open(orig_json, 'r', encoding='utf-8') as f:
                meta = _json.load(f)

        meta['audio_path'] = os.path.abspath(orig_mp3)
        meta['replay_of']  = folder

        out_json = os.path.join(output_dir, 'episode.json')
        with open(out_json, 'w', encoding='utf-8') as f:
            _json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"  Replay: {folder} → {output_dir}")
        created.append(out_json)

    return created


def _run_spot_source(source_config: dict, config: dict, is_first_of_day: bool) -> str | None:
    import json as _json
    from src.spots import get_next_spot
    from pydub import AudioSegment as _AS
    import io as _io

    source_name = source_config.get('name', 'Comunicado')
    output_dir  = _episode_output_dir(source_config['id'])

    print(f"\n{'='*50}")
    print(f"Fonte: {source_name} (spot)")
    print(f"{'='*50}")

    result = get_next_spot()
    if not result:
        print("  Nenhum spot disponivel ou todos atingiram o limite diario.")
        return None

    spot, audio_bytes = result
    os.makedirs(output_dir, exist_ok=True)
    episode_path = os.path.join(output_dir, 'episode.mp3')

    with open(episode_path, 'wb') as f:
        f.write(audio_bytes)

    try:
        duration = len(_AS.from_mp3(_io.BytesIO(audio_bytes))) / 1000
    except Exception:
        duration = len(audio_bytes) / 16000

    metadata = {
        'source_name':      source_name,
        'duration_seconds': int(duration),
        'videos_covered':   1,
        'links': [{'title': spot.get('id', ''), 'url': '', 'channel': 'Spots',
                   'views': 0, 'published_at': '', 'top_comments': []}],
        'spot_id':   spot['id'],
        'spot_type': spot.get('type', 'file'),
    }
    with open(os.path.join(output_dir, 'episode.json'), 'w', encoding='utf-8') as f:
        _json.dump(metadata, f, ensure_ascii=False, indent=2)

    mins, secs = int(duration // 60), int(duration % 60)
    print(f"\nSpot gerado: {episode_path}")
    print(f"Duracao: {mins}m {secs}s | ID: {spot['id']} ({spot.get('type', 'file')})")
    return episode_path


def _web_radio_transcribe(episode_path: str, settings: dict, output_dir: str) -> str:
    """Transcreve os primeiros N segundos do MP3 via Groq Whisper."""
    import requests as _req
    from pydub import AudioSegment

    api_key_env = settings.get('transcribe_api_key_env', 'GROQ_API_KEY')
    api_key     = os.getenv(api_key_env, '')
    if not api_key:
        print(f"  [web-radio] {api_key_env} não encontrada — transcrição indisponível.")
        return ''

    seconds   = int(settings.get('transcribe_seconds', 90))
    temp_path = os.path.join(output_dir, '_transcribe_tmp.mp3')
    try:
        audio   = AudioSegment.from_mp3(episode_path)
        excerpt = audio[:seconds * 1000]
        excerpt.export(temp_path, format='mp3')
    except Exception as e:
        print(f"  [web-radio] Erro ao extrair trecho para transcrição: {e}")
        return ''

    try:
        print(f"  [web-radio] Transcrevendo primeiros {seconds}s via Groq Whisper...")
        with open(temp_path, 'rb') as f:
            resp = _req.post(
                'https://api.groq.com/openai/v1/audio/transcriptions',
                headers={'Authorization': f'Bearer {api_key}'},
                files={'file': ('audio.mp3', f, 'audio/mpeg')},
                data={'model': 'whisper-large-v3', 'language': 'pt',
                      'response_format': 'text'},
                timeout=60,
            )
            resp.raise_for_status()
            text = resp.text.strip()
            print(f"  [web-radio] Transcrição: {text[:100]}{'...' if len(text) > 100 else ''}")
            return text
    except Exception as e:
        print(f"  [web-radio] Erro na transcrição Groq: {e}")
        return ''
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _web_radio_intro_text(source_config: dict, config: dict,
                           episode_path: str = '', output_dir: str = '') -> str:
    """Resolve o texto da intro conforme intro_mode configurado."""
    settings    = source_config.get('settings') or {}
    intro_mode  = settings.get('intro_mode', '').strip()
    intro_text  = settings.get('intro_text', '').strip()
    source_name = source_config.get('name', 'Rádio Externa')

    if intro_mode == 'fixed':
        return intro_text or f"E agora, {source_name}."

    if intro_mode in ('llm', 'transcribe'):
        import litellm
        radio_name = config.get('radio', {}).get('name', 'RadioIA')
        llm_cfg    = config.get('llm', config.get('claude', {}))
        model      = source_config.get('model') or llm_cfg.get('model', 'claude-haiku-4-5-20251001')
        context    = source_config.get('context', '')

        if intro_mode == 'transcribe' and episode_path and output_dir:
            transcription = _web_radio_transcribe(episode_path, settings, output_dir)
            if transcription:
                context_line = (
                    f"\n\nTranscrição dos primeiros instantes do áudio:\n\"{transcription}\""
                )
            else:
                context_line = f"\nContexto adicional: {context}" if context else ''
        else:
            context_line = f"\nContexto adicional: {context}" if context else ''

        prompt = (
            f"Você é o locutor da rádio {radio_name}. "
            f"Crie uma apresentação curta (1 a 2 frases) para introduzir o bloco '{source_name}' "
            f"que será reproduzido a seguir.{context_line}\n"
            f"Responda apenas com o texto da locução, sem aspas nem explicações."
        )
        try:
            resp = litellm.completion(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=120,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"  [web-radio] Erro ao gerar intro via LLM: {e}")
            return f"E agora, {source_name}."

    return ''


def _web_radio_prepend_intro(intro_text: str, external_mp3: str,
                              output_dir: str, config: dict) -> None:
    """Gera TTS da intro_text e concatena antes do external_mp3 (in-place)."""
    from src.tts_generator import parse_script, generate_audio_files
    from pydub import AudioSegment

    narrators = config.get('narrators', [{}])
    narrator  = narrators[0]
    voices    = {'LOCUTOR_A': narrator.get('voice', 'pt-BR-FranciscaNeural')}
    tts_cfg   = config.get('tts', {})

    script = f'[LOCUTOR_A]: {intro_text}'
    lines  = parse_script(script)
    if not lines:
        return

    print(f"  [web-radio] Gerando intro TTS: \"{intro_text[:60]}\"")
    temp_dir = os.path.join(output_dir, '_intro_tmp')
    try:
        paths, _ = generate_audio_files(lines, voices, temp_dir, tts_cfg)
        if not paths:
            return

        intro_seg   = sum((AudioSegment.from_mp3(p) for p in paths), AudioSegment.empty())
        external_seg = AudioSegment.from_mp3(external_mp3)
        combined    = intro_seg + external_seg
        combined.export(external_mp3, format='mp3')
        print(f"  [web-radio] Intro concatenada ({len(intro_seg)/1000:.1f}s + {len(external_seg)/1000:.1f}s)")
    except Exception as e:
        print(f"  [web-radio] Erro ao gerar intro: {e} — continuando sem intro.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _run_web_radio_source(source_config: dict, config: dict) -> str | None:
    source_id   = source_config['id']
    source_name = source_config.get('name', 'Rádio Externa')
    output_dir  = _episode_output_dir(source_id)

    print(f"\n{'='*50}")
    print(f"Fonte: {source_name} (web_radio)")
    print(f"{'='*50}")

    _inicio = _local_now().strftime('%H:%M:%S')
    _write_status(source_id, source_name, 'buscando', inicio=_inicio)

    plugin = SOURCE_MODULES.get('web_radio')
    if not plugin:
        print("  [web-radio] Plugin não carregado.")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro='plugin não carregado')
        return None

    items = plugin.fetch(source_config)
    if not items:
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro='sem audio disponivel')
        return None

    item      = items[0]
    audio_url = item.get('audio_url', '') or item.get('url', '')
    if not audio_url:
        print("  [web-radio] URL de áudio não encontrada.")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro='url de audio ausente')
        return None

    _write_status(source_id, source_name, 'baixando', inicio=_inicio)
    os.makedirs(output_dir, exist_ok=True)
    episode_path = os.path.join(output_dir, 'episode.mp3')

    try:
        import requests as _req
        ua      = (source_config.get('settings') or {}).get(
            'user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        timeout = int((source_config.get('settings') or {}).get('timeout', 30))
        with _req.get(audio_url, headers={'User-Agent': ua}, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(episode_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        print(f"  [web-radio] Erro ao baixar MP3: {e}")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro=str(e))
        return None

    intro_text = _web_radio_intro_text(source_config, config,
                                        episode_path=episode_path,
                                        output_dir=output_dir)
    if intro_text:
        _write_status(source_id, source_name, 'narrando intro', inicio=_inicio)
        _web_radio_prepend_intro(intro_text, episode_path, output_dir, config)

    size_mb = os.path.getsize(episode_path) / (1024 * 1024)

    from src.audio_mixer import save_episode_metadata
    try:
        from pydub.utils import mediainfo
        info     = mediainfo(episode_path)
        duration = float(info.get('duration', 0))
    except Exception:
        duration = 0.0

    save_episode_metadata(
        videos=[item], script=intro_text, output_dir=output_dir,
        duration_secs=duration, source_name=source_name,
    )

    _write_status(source_id, source_name, 'concluido', ativo=False, inicio=_inicio)

    mins, secs = int(duration // 60), int(duration % 60)
    print(f"\nEpisodio de relay gerado: {episode_path}")
    print(f"Tamanho: {size_mb:.1f} MB | Duracao: {mins}m {secs}s")
    return episode_path


def _run_music_source(source_config: dict, config: dict, is_first_of_day: bool) -> str | None:
    source_id   = source_config['id']
    source_name = source_config.get('name', 'Selecao Musical')
    output_dir  = _episode_output_dir(source_id)
    radio_name  = config.get('radio', {}).get('name', 'RadioIA')

    print(f"\n{'='*50}")
    print(f"Fonte: {source_name} (music)")
    print(f"{'='*50}")

    _inicio = _local_now().strftime('%H:%M:%S')
    _write_status(source_id, source_name, 'mixando', inicio=_inicio)

    narrators = config['narrators'][:1]
    try:
        duration = music_source.generate_episode(
            source_config, output_dir, narrators, is_first_of_day, station_name=radio_name
        )
    except FileNotFoundError as e:
        print(f"  Erro: {e}")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro=str(e))
        return None

    _write_status(source_id, source_name, 'concluido', ativo=False, inicio=_inicio)

    episode_path = os.path.join(output_dir, 'episode.mp3')
    mins, secs = int(duration // 60), int(duration % 60)
    print(f"\nBloco musical gerado: {episode_path}")
    print(f"Duracao: {mins}m {secs}s")
    return episode_path


def _run_utility_source(source_config: dict, config: dict, is_first_of_day: bool) -> str | None:
    source_id   = source_config['id']
    source_name = source_config.get('name', 'Resumo do Dia')
    output_dir  = _episode_output_dir(source_id)
    radio_name  = config.get('radio', {}).get('name', 'RadioIA')

    print(f"\n{'='*50}")
    print(f"Fonte: {source_name} (utility)")
    print(f"{'='*50}")

    _inicio   = _local_now().strftime('%H:%M:%S')
    _write_status(source_id, source_name, 'buscando', inicio=_inicio)

    narrators = config['narrators'][:2]
    llm_cfg   = config.get('llm', config.get('claude', {}))
    tts_cfg   = config.get('tts', {})

    def _status(etapa: str, progresso: str = ''):
        _write_status(source_id, source_name, etapa, progresso=progresso, inicio=_inicio)

    try:
        duration = utility_source.generate_episode(
            source_config, output_dir, narrators, is_first_of_day,
            station_name=radio_name,
            llm_config=llm_cfg,
            tts_config=tts_cfg,
            status_callback=_status,
        )
    except Exception as e:
        print(f"  Erro: {e}")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro=str(e))
        return None

    _write_status(source_id, source_name, 'concluido', ativo=False, inicio=_inicio)

    episode_path = os.path.join(output_dir, 'episode.mp3')
    mins, secs = int(duration // 60), int(duration % 60)
    print(f"\nBloco de utilidades gerado: {episode_path}")
    print(f"Duracao: {mins}m {secs}s")
    return episode_path


def _run_combined_source(source_config: dict, config: dict, credentials,
                         seen_ids: set, is_first_of_day: bool, publish: bool = True) -> str | None:
    source_id   = source_config['id']
    source_name = source_config['name']
    sub_ids     = source_config.get('sources', [])
    all_sources = config.get('sources', [])
    output_dir  = _episode_output_dir(source_id)
    temp_dir    = os.path.join(output_dir, 'temp')
    _begin_log(output_dir)

    print(f"\n{'='*50}")
    print(f"Fonte: {source_name} (combined)")
    print(f"{'='*50}")
    _start_dt = _local_now()
    _inicio = _start_dt.strftime('%H:%M:%S')
    _write_status(source_id, source_name, 'buscando', inicio=_inicio)

    items = []
    for sub_id in sub_ids:
        sub_cfg = next((s for s in all_sources if s['id'] == sub_id), None)
        if not sub_cfg:
            print(f"  [combined] sub-fonte '{sub_id}' nao encontrada — ignorando")
            continue
        sub_type = sub_cfg.get('type', '')
        module   = SOURCE_MODULES.get(sub_type)
        if not module or not hasattr(module, 'fetch'):
            print(f"  [combined] tipo '{sub_type}' nao suporta fetch() — ignorando '{sub_id}'")
            continue
        try:
            if sub_type == 'youtube':
                sub_cfg = {**sub_cfg, '_api_key': os.getenv('YOUTUBE_API_KEY')}
                sub_items = module.fetch(sub_cfg, credentials)
            else:
                sub_items = module.fetch(sub_cfg)
            valid = [v for v in sub_items if v.get('id')]
            print(f"  [{sub_id}]: {len(valid)} item(s)")
            items.extend(valid)
        except Exception as e:
            print(f"  [combined/{sub_id}] erro ao buscar: {e}")

    before = len(items)
    items  = [v for v in items if v['id'] not in seen_ids]
    if before - len(items):
        print(f"  {before - len(items)} item(s) ignorado(s) — ja citados.")

    if not items:
        print("  Nenhum conteudo novo encontrado.")
        _write_status(source_id, source_name, 'concluido',
                      progresso='sem conteudo novo', ativo=False, inicio=_inicio)
        _end_log(); return None

    print(f"  {len(items)} item(s) total.\n")
    _write_status(source_id, source_name, 'llm', progresso=f'{len(items)} itens', inicio=_inicio)

    narrators  = config['narrators'][:3]
    radio_name = config.get('radio', {}).get('name', 'RadioIA')
    llm_cfg    = config.get('llm', config.get('claude', {}))
    model      = source_config.get('model') or llm_cfg.get('model', 'claude-sonnet-4-6')
    api_base   = llm_cfg.get('api_base')

    print(f"Gerando roteiro ({model})...")
    _llm_t0 = _local_now()
    script, llm_usage = generate_script(
        items, narrators,
        {**source_config, 'type': 'combined'},
        is_first_of_day=is_first_of_day,
        station_name=radio_name,
        model=model,
        api_base=api_base,
        generation_time=_inicio[:5],
        prompt_log_path=os.path.join(output_dir, 'prompt.txt'),
    )
    _llm_t1 = _local_now()
    print(f"  {len(script.split())} palavras.\n")

    print("Gerando audio...")
    lines = parse_script(script)
    if not lines:
        print("  Roteiro sem falas no formato esperado.")
        _write_status(source_id, source_name, 'erro',
                      progresso='roteiro sem falas', ativo=False, inicio=_inicio)
        _end_log(); return None

    _write_status(source_id, source_name, 'tts', progresso=f'{len(lines)} falas', inicio=_inicio)
    locutor_keys = ['LOCUTOR_A', 'LOCUTOR_B', 'LOCUTOR_C']
    voices       = {key: narrators[min(i, len(narrators) - 1)]['voice'] for i, key in enumerate(locutor_keys)}
    tts_config   = config.get('tts', {})
    _tts_t0 = _local_now()
    try:
        audio_files, tts_usage = generate_audio_files(lines, voices, temp_dir, tts_config)
    except Exception as e:
        print(f"  [tts] Erro: {e}")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro=str(e))
        _end_log()
        return None
    _tts_t1 = _local_now()

    vinheta_config = {**config.get('vinheta', {}), 'station_name': radio_name}
    vinhetas = generate_vinhetas(vinheta_config, temp_dir, tts_config)
    print(f"  {len(lines)} falas + vinhetas.\n")

    print("Montando episodio...")
    _write_status(source_id, source_name, 'mixando', inicio=_inicio)
    os.makedirs(output_dir, exist_ok=True)
    episode_path = os.path.join(output_dir, 'episode.mp3')
    episode_id   = '/'.join(output_dir.replace('\\', '/').split('/')[-2:])
    links_text   = ' | '.join(f"[{i}] {v['title']} {v['url']}" for i, v in enumerate(items, 1))

    item_timestamps = {}
    _mix_t0 = _local_now()
    duration = mix_episode(
        audio_files=audio_files,
        lines=lines,
        output_path=episode_path,
        metadata={'title': f'{source_name} - {episode_id}', 'links_text': links_text},
        radio_config=config.get('radio', {}),
        vinhetas=vinhetas,
        station_name=radio_name,
        item_timestamps=item_timestamps,
    )
    _mix_t1 = _local_now()

    _write_status(source_id, source_name, 'finalizando', inicio=_inicio)
    _generation = {
        'model':         model,
        'started_at':    _start_dt.isoformat(timespec='seconds'),
        'finished_at':   _mix_t1.isoformat(timespec='seconds'),
        'total_seconds': round((_mix_t1 - _start_dt).total_seconds()),
        'llm_seconds':   round((_llm_t1 - _llm_t0).total_seconds()),
        'tts_seconds':   round((_tts_t1 - _tts_t0).total_seconds()),
        'mix_seconds':   round((_mix_t1 - _mix_t0).total_seconds()),
        'script_words':  len(script.split()),
        'items_count':   len(items),
        'tts':           tts_usage,
    }
    if llm_usage:
        _generation.update(llm_usage)
    save_episode_metadata(items, script, output_dir, duration, source_name=source_name,
                          item_timestamps=item_timestamps, generation=_generation, publish=publish)
    save_episode_to_history(episode_id, items)
    shutil.rmtree(temp_dir, ignore_errors=True)
    _write_status(source_id, source_name, 'concluido', ativo=False, inicio=_inicio, publicar=publish)

    mins, secs = int(duration // 60), int(duration % 60)
    draft_note = ' [RASCUNHO]' if not publish else ''
    print(f"\nEpisodio combinado pronto{draft_note}: {episode_path}")
    print(f"Duracao: {mins}m {secs}s | Itens: {len(items)}")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item['title'][:60]}")
        print(f"      {item.get('url', '')}")
    _end_log(); return episode_path


def _run_source(source_config: dict, config: dict, credentials, seen_ids: set,
                is_first_of_day: bool = True, publish: bool = True) -> str | None:
    source_type = source_config['type']
    source_id = source_config['id']
    source_name = source_config['name']
    module = SOURCE_MODULES.get(source_type)

    if not module:
        print(f"  Tipo desconhecido: {source_type}")
        return None

    youtube_api_key = os.getenv('YOUTUBE_API_KEY')

    output_dir = _episode_output_dir(source_id)
    temp_dir   = os.path.join(output_dir, 'temp')
    episode_id = '/'.join(output_dir.replace('\\', '/').split('/')[-2:])
    _begin_log(output_dir)

    print(f"\n{'='*50}")
    print(f"Fonte: {source_name} ({source_type})")
    print(f"{'='*50}")
    _start_dt = _local_now()
    _inicio = _start_dt.strftime('%H:%M:%S')
    _write_status(source_id, source_name, 'buscando', inicio=_inicio)

    # Inject API key for YouTube source
    if source_type == 'youtube':
        source_config = {**source_config, '_api_key': youtube_api_key}
        items = module.fetch(source_config, credentials)
    else:
        items = module.fetch(source_config)

    before = len(items)
    items = [v for v in items if v['id'] not in seen_ids]
    skipped = before - len(items)
    if skipped:
        print(f"  {skipped} item(s) ignorado(s) — ja citados anteriormente.")

    # Clipping: limita ao max_sources APÓS o filtro de histórico
    if source_type in ('clipping', 'clipping_auto'):
        max_sources = int((source_config.get('settings') or {}).get('max_sources', 5))
        items = items[:max_sources]

    # RSS: fetch() agora retorna candidatos de todos os feeds sem early-stop.
    # Aplica max_total aqui, após o filtro de seen_ids, para que feeds
    # consultados mais tarde também contribuam com itens novos.
    if source_type == 'rss':
        max_rss = int((source_config.get('settings') or {}).get('max_items_total', 10))
        items = items[:max_rss]

    # megacurioso: fetch() retorna o pool (fetch_count); max_items limita o episodio
    if source_type == 'megacurioso':
        max_mc = int((source_config.get('settings') or {}).get('max_items', 1))
        items = items[:max_mc]

    # Se poucos itens novos, expande o periodo de busca e complementa
    # (não se aplica a fontes com número fixo de itens como horoscopo/trivia)
    settings = source_config.get('settings') or {}
    max_total = settings.get('max_videos_total', settings.get('max_items_total', 10))
    min_items = max(3, max_total // 3)

    if 0 < len(items) < min_items and source_type not in ('horoscopo', 'trivia', 'efemerides'):
        lookback = settings.get('days_lookback', 7)
        print(f"  Poucos itens novos ({len(items)}), expandindo busca para {lookback * 3} dias...")
        expanded_settings = {**settings, 'days_lookback': lookback * 3}
        expanded_config = {**source_config, 'settings': expanded_settings}

        already_ids = seen_ids | {v['id'] for v in items}
        if source_type == 'youtube':
            extra = module.fetch(expanded_config, credentials)
        else:
            extra = module.fetch(expanded_config)

        extra_new = [v for v in extra if v['id'] not in already_ids]
        needed = max_total - len(items)
        items.extend(extra_new[:needed])
        if extra_new:
            print(f"  +{min(len(extra_new), needed)} item(s) encontrado(s) na busca expandida.")

    if not items:
        print("  Nenhum conteudo novo encontrado.")
        _write_status(source_id, source_name, 'concluido',
                      progresso='sem conteudo novo', ativo=False, inicio=_inicio)
        _end_log(); return None

    print(f"  {len(items)} item(s) novo(s).\n")
    _write_status(source_id, source_name, 'llm',
                  progresso=f'{len(items)} itens', inicio=_inicio)

    narrators = config['narrators'][:3]
    radio_name = config.get('radio', {}).get('name', 'RadioIA')
    llm_cfg = config.get('llm', config.get('claude', {}))
    default_model = llm_cfg.get('model', 'claude-sonnet-4-6')
    api_base = llm_cfg.get('api_base')
    model = source_config.get('model') or default_model

    print(f"Gerando roteiro ({model})...")
    _llm_t0 = _local_now()
    script, llm_usage = generate_script(items, narrators, source_config,
                                        is_first_of_day=is_first_of_day, station_name=radio_name,
                                        model=model, api_base=api_base,
                                        generation_time=_inicio[:5],
                                        prompt_log_path=os.path.join(output_dir, 'prompt.txt'))
    _llm_t1 = _local_now()
    print(f"  {len(script.split())} palavras.\n")

    print("Gerando audio...")
    lines = parse_script(script)
    if not lines:
        print("  Roteiro sem falas no formato esperado.")
        print(script[:400])
        _write_status(source_id, source_name, 'erro',
                      progresso='roteiro sem falas', ativo=False, inicio=_inicio)
        _end_log(); return None
    _write_status(source_id, source_name, 'tts',
                  progresso=f'{len(lines)} falas', inicio=_inicio)

    locutor_keys = ['LOCUTOR_A', 'LOCUTOR_B', 'LOCUTOR_C']
    voices = {key: narrators[min(i, len(narrators) - 1)]['voice'] for i, key in enumerate(locutor_keys)}
    tts_config = config.get('tts', {})
    _tts_t0 = _local_now()
    try:
        audio_files, tts_usage = generate_audio_files(lines, voices, temp_dir, tts_config)
    except Exception as e:
        print(f"  [tts] Erro: {e}")
        _write_status(source_id, source_name, 'erro', ativo=False, inicio=_inicio, erro=str(e))
        _end_log()
        return None
    _tts_t1 = _local_now()

    vinheta_config = {**config.get('vinheta', {}), 'station_name': radio_name}
    vinhetas = generate_vinhetas(vinheta_config, temp_dir, tts_config)
    print(f"  {len(lines)} falas + vinhetas geradas.\n")

    print("Montando episodio...")
    _write_status(source_id, source_name, 'mixando', inicio=_inicio)
    episode_path = os.path.join(output_dir, 'episode.mp3')
    links_text = ' | '.join(f"[{i}] {v['title']} {v['url']}" for i, v in enumerate(items, 1))

    item_timestamps = {}
    _mix_t0 = _local_now()
    duration = mix_episode(
        audio_files=audio_files,
        lines=lines,
        output_path=episode_path,
        metadata={'title': f'{source_name} - {episode_id}', 'links_text': links_text},
        radio_config=config.get('radio', {}),
        vinhetas=vinhetas,
        station_name=radio_name,
        item_timestamps=item_timestamps,
    )
    _mix_t1 = _local_now()

    _write_status(source_id, source_name, 'finalizando', inicio=_inicio)
    _generation = {
        'model':         model,
        'started_at':    _start_dt.isoformat(timespec='seconds'),
        'finished_at':   _mix_t1.isoformat(timespec='seconds'),
        'total_seconds': round((_mix_t1 - _start_dt).total_seconds()),
        'llm_seconds':   round((_llm_t1 - _llm_t0).total_seconds()),
        'tts_seconds':   round((_tts_t1 - _tts_t0).total_seconds()),
        'mix_seconds':   round((_mix_t1 - _mix_t0).total_seconds()),
        'script_words':  len(script.split()),
        'items_count':   len(items),
        'tts':           tts_usage,
    }
    if llm_usage:
        _generation.update(llm_usage)
    save_episode_metadata(items, script, output_dir, duration, source_name=source_name,
                          item_timestamps=item_timestamps, generation=_generation, publish=publish)
    save_episode_to_history(episode_id, items)
    shutil.rmtree(temp_dir)
    _write_status(source_id, source_name, 'concluido', ativo=False, inicio=_inicio, publicar=publish)

    mins, secs = int(duration // 60), int(duration % 60)
    draft_note = ' [RASCUNHO]' if not publish else ''
    print(f"\nEpisodio pronto{draft_note}: {episode_path}")
    print(f"Duracao: {mins}m {secs}s | Itens: {len(items)}")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item['title'][:60]}")
        print(f"      {item['url']}")
    _end_log(); return episode_path


def _cmd_gen_time_clips():
    from src.time_clips import generate_atomic_clips
    config = load_config()
    vinheta = config.get('vinheta', {})
    voice   = vinheta.get('voice', 'pt-BR-FranciscaNeural')
    rate    = vinheta.get('rate',  '+15%')
    print(f"Gerando clips de hora/minuto (voz: {voice}, rate: {rate})...")
    force = '--force' in sys.argv
    n = generate_atomic_clips(voice=voice, rate=rate, force=force)
    if n:
        print(f"  {n} clip(s) gerado(s) em output/_time_clips/atomic/")
    else:
        print("  Todos os clips já existem. Use --gen-time-clips --force para regenerar.")


def _cmd_download_musica():
    config = load_config()
    from src.sources import music as music_source
    jamendo_sources = [
        s for s in config.get('sources', [])
        if s.get('type') == 'music'
        and (s.get('settings') or {}).get('source') == 'jamendo'
    ]
    if not jamendo_sources:
        print("Nenhuma fonte de música Jamendo configurada no config.yaml.")
        return
    for src in jamendo_sources:
        print(f"Baixando músicas — {src.get('name', src['id'])}...")
        n = music_source.download_cache(src)
        print(f"  {n} faixa(s) nova(s) baixada(s).\n")


def main():
    if '--gen-time-clips' in sys.argv:
        _cmd_gen_time_clips()
        sys.exit(0)

    if 'download-musica' in sys.argv:
        _cmd_download_musica()
        sys.exit(0)

    # 'listar-assuntos' → descobre tópicos dos feeds e lista sem gerar episódio
    if 'listar-assuntos' in sys.argv[1:]:
        import plugins.clipping_auto as ca
        from datetime import date as _date
        argv_rest = sys.argv[sys.argv.index('listar-assuntos') + 1:]
        categoria   = argv_rest[0] if argv_rest and not argv_rest[0].startswith('-') else ''
        max_topicos = int(argv_rest[1]) if len(argv_rest) > 1 and argv_rest[1].isdigit() else 10
        cfg = load_config()
        api_base = (cfg.get('llm') or cfg.get('claude') or {}).get('api_base')
        sources  = cfg.get('sources', [])
        ca_src   = next((s for s in sources if s.get('type') == 'clipping_auto'), {})
        feeds    = (ca_src.get('settings') or {}).get('trending_feeds', ca.DEFAULT_TRENDING_FEEDS)
        cat_label = f' [{categoria}]' if categoria else ''
        print(f"Coletando manchetes de {len(feeds)} feed(s)...")
        headlines = ca._collect_headlines(feeds, _date.today())
        print(f"{len(headlines)} manchete(s). Consultando LLM{cat_label}...")
        topics = ca._discover_topics(headlines, max_topicos, [], categoria, ca.DEFAULT_LLM_MODEL, api_base)
        if not topics:
            print("Nenhum topico encontrado.")
        else:
            print(f"\nPrincipais assuntos{cat_label}:")
            for i, t in enumerate(topics, 1):
                print(f"  {i:2}. {t}")
                print(f'      python main.py clipping:"{t}"')
        sys.exit(0)

    # 'replay' sem parâmetro → lista episódios do dia disponíveis para replay
    if 'replay' in sys.argv[1:] and not any(a.startswith('replay:') for a in sys.argv[1:]):
        today = _local_now().strftime('%Y-%m-%d')
        day_dir = os.path.join('output', today)
        if not os.path.isdir(day_dir):
            print(f"Nenhum episodio encontrado para hoje ({today}).")
        else:
            folders = sorted([
                f for f in os.listdir(day_dir)
                if os.path.isdir(os.path.join(day_dir, f))
                and os.path.exists(os.path.join(day_dir, f, 'episode.mp3'))
            ])
            if not folders:
                print(f"Nenhum episodio com audio disponivel para hoje ({today}).")
            else:
                print(f"Episodios disponiveis para replay em {today}:")
                for f in folders:
                    print(f"  python main.py replay:{f}")
        sys.exit(0)

    config = load_config()
    radio_name = config.get('radio', {}).get('name', 'RadioIA')
    print(f"{radio_name}\n")
    youtube_api_key = os.getenv('YOUTUBE_API_KEY')

    if not youtube_api_key:
        print("Erro: configure YOUTUBE_API_KEY no arquivo .env")
        sys.exit(1)

    # CLI: python main.py [source_id[:param] ...]
    # Exemplos: youtube  |  musica  |  musica:3  |  musica:1
    def _parse_cli(args: list[str]) -> dict[str, str | None]:
        result = {}
        for arg in args:
            if ':' in arg:
                sid, param = arg.split(':', 1)
                result[sid] = param
            else:
                result[arg] = None
        return result

    # Filtra flags (--flag) antes de parsear — não são IDs de fonte
    cli_args = [a for a in sys.argv[1:] if not a.startswith('--')]

    # Extrai |contexto de args não-especiais (ex: "youtube|foca em tecnologia")
    _cli_contexts: dict[str, str] = {}
    for _arg in cli_args:
        if _arg.startswith(('url:', 'replay:', 'clipping:')):
            continue
        _base, _, _ctx = _arg.partition('|')
        if _ctx:
            _cli_contexts[_base.split(':', 1)[0]] = _ctx
    # Remove sufixo |contexto dos args para que _parse_cli leia só o source_id[:param]
    cli_args = [a.partition('|')[0] if '|' in a and not a.startswith('url:') else a for a in cli_args]

    # 'clipping|tema' (Admin UI) → 'clipping:tema' (formato nativo do CLI)
    cli_args = [
        f"clipping:{_cli_contexts.pop(a)}" if a == 'clipping' and a in _cli_contexts else a
        for a in cli_args
    ]

    cli = _parse_cli(cli_args) if cli_args else {}

    # Extrai replay: direto do argv para suportar múltiplos (replay:X replay:Y)
    replay_targets = [a.split(':', 1)[1] for a in sys.argv[1:] if a.startswith('replay:')]
    # Extrai URLs avulsas: url:https://... → fonte sintética, sem precisar de config
    # Usa cli_args diretamente (não dict) para suportar múltiplos url: no mesmo comando
    url_targets = [a.split(':', 1)[1] for a in cli_args if a.startswith('url:')]
    # Extrai clippings: clipping:tema → fonte sintética, sem precisar de config
    clipping_targets = [v for k, v in cli.items() if k == 'clipping' and v]
    if any(k == 'clipping' and not v for k, v in cli.items()):
        print("'clipping' requer um tópico. Use: python main.py \"clipping:reforma tributaria\"")
        print("No Admin UI: selecione Clipping e preencha o campo de contexto com o tema.")
        sys.exit(1)
    cli_clean   = {k: v for k, v in cli.items() if k not in ('url', 'replay', 'clipping')}
    requested   = set(cli_clean.keys())

    all_sources = config.get('sources', [])
    if requested:
        sources = [s for s in all_sources if s['id'] in requested]
        unknown = requested - {s['id'] for s in all_sources}
        if unknown:
            available = ', '.join(s['id'] for s in all_sources)
            print(f"Fonte(s) desconhecida(s): {', '.join(unknown)}")
            print(f"Disponiveis: {available}")
            sys.exit(1)
    elif not url_targets and not clipping_targets and not replay_targets:
        print("Nenhuma fonte especificada. Use: python main.py <fonte> [<fonte2> ...]")
        print(f"Disponiveis: {', '.join(s['id'] for s in all_sources)}")
        sys.exit(1)
    else:
        sources = []

    for raw in url_targets:
        url_part, _, ctx = raw.partition('|')
        sources.append({
            'id':       'url',
            'type':     'url',
            'name':     'Conteúdo da Web',
            'enabled':  True,
            'settings': {'url': url_part.strip()},
            'context':  ctx.strip(),
        })

    followup = '--followup' in sys.argv
    for topic in clipping_targets:
        # Mescla defaults do config (se existir fonte id=clipping) com o tópico CLI
        base = next((s for s in all_sources if s['id'] == 'clipping'), {})
        sources.append({
            **base,
            'id':      'clipping',
            'type':    'clipping',
            'name':    f"Clipping — {topic[:60]}",
            'enabled': True,
            'settings': {**(base.get('settings') or {}), 'topic': topic, 'followup': followup},
        })

    if not sources and not replay_targets:
        print("Nenhuma fonte selecionada ou habilitada.")
        sys.exit(0)

    credentials = _get_oauth_credentials()
    if credentials:
        print("OAuth ativo — inscricoes do YouTube disponiveis.\n")
    else:
        print("Sem OAuth — usando canais configurados.\n")

    if '--draft' in sys.argv:
        publish = False
    else:
        publish = not config.get('llm', {}).get('draft', False)
    if not publish:
        print("Modo rascunho ativado — episodios nao serao publicados no player.\n")

    seen_ids = load_seen_ids()
    generated = []
    first_of_day = not _has_episodes_today()

    for source_config in sources:
        # Apply CLI param overrides
        param = cli.get(source_config['id'])

        # Injeta _param para que qualquer plugin possa acessar o parâmetro CLI
        if param is not None:
            source_config = {**source_config, '_param': param}

        # Injeta contexto CLI (|contexto) — sobrescreve config.yaml se informado
        if source_config['id'] in _cli_contexts:
            source_config = {**source_config, 'context': _cli_contexts[source_config['id']]}

        if param is not None and source_config.get('type') == 'music':
            try:
                n = int(param)
                source_config = {
                    **source_config,
                    'settings': {**source_config.get('settings', {}), 'num_tracks': n}
                }
                print(f"  Parametro CLI: {n} musica(s)")
            except ValueError:
                print(f"  Parametro invalido '{param}' — usando config padrao.")

        if param is not None and source_config.get('type') == 'clipping':
            source_config = {
                **source_config,
                'settings': {**(source_config.get('settings') or {}), 'topic': param},
                'name': f"Clipping — {param[:60]}",
            }
            print(f"  Tópico: {param}")

        if param is not None and source_config.get('type') == 'horoscopo':
            try:
                from plugins.horoscopo import SIGN_PAIRS, SIGN_PT
                n = int(param) % 6
                pair = SIGN_PAIRS[n]
                label = f"{SIGN_PT[pair[0]]} e {SIGN_PT[pair[1]]}"
                source_config = {
                    **source_config,
                    'settings': {**(source_config.get('settings') or {}), 'pair_index': n},
                    'name': f"Horóscopo — {label}",
                }
                print(f"  Parametro CLI: par {n} ({label})")
            except ValueError:
                print(f"  Parametro invalido '{param}' — usando rotacao automatica.")

        if source_config.get('type') == 'web_radio':
            path = _run_web_radio_source(source_config, config)
            if path:
                generated.append(path)
                first_of_day = False
            continue

        if source_config.get('type') in ('music', 'utility', 'spot'):
            fn = {'music': _run_music_source,
                  'utility': _run_utility_source,
                  'spot': _run_spot_source}[source_config['type']]
            path = fn(source_config, config, first_of_day)
            if path:
                generated.append(path)
                first_of_day = False
            continue

        if source_config.get('type') == 'combined':
            path = _run_combined_source(source_config, config, credentials, seen_ids, first_of_day,
                                        publish=publish)
            if path:
                generated.append(path)
                first_of_day = False
                seen_ids = load_seen_ids()
            continue

        path = _run_source(source_config, config, credentials, seen_ids,
                           is_first_of_day=first_of_day, publish=publish)
        if path:
            generated.append(path)
            first_of_day = False  # subsequent sources are mid-day segments
            seen_ids = load_seen_ids()

    for partial in replay_targets:
        print(f"\n{'='*50}")
        print(f"Replay: '{partial}'")
        print(f"{'='*50}")
        paths = _run_replay_cli(partial)
        generated.extend(paths)

    print(f"\n{'='*50}")
    print(f"Concluido. {len(generated)} episodio(s) gerado(s).")
    for p in generated:
        print(f"  {p}")


if __name__ == '__main__':
    main()
