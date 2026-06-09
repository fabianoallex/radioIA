"""
Podcast source — transcreve e resume episódios de podcast via RSS, URL direta ou YouTube.

Parâmetros (settings em config.yaml):
  url                  — RSS feed, URL direta do MP3/áudio ou URL de vídeo do YouTube
  max_items            — episódios a buscar do feed RSS (default: 1)
  days_lookback        — janela de busca no RSS em dias (default: 7)
  show_notes_min_chars — mínimo de chars nas show notes antes de usar Whisper (default: 500)
  whisper_start        — início do trecho a transcrever, em segundos (default: 0)
  whisper_duration     — duração do trecho a transcrever, em segundos (default: 600 = 10min)
  topic                — tema específico para focar no roteiro (opcional)
  whisper_model        — tamanho do modelo Whisper: tiny/base/small/medium/large (default: base)

Uso via CLI (sobrescreve settings):
  python main.py podcast:https://feeds.example.com/feed.rss
  python main.py podcast:https://www.youtube.com/watch?v=XXXX
  python main.py podcast:url=https://...,start=300,duration=600,topic=IA
  python main.py podcast-tech:start=120,topic=privacidade

Dependências opcionais:
  pip install openai-whisper   — transcrição de áudio via Whisper
  pip install yt-dlp           — download de áudio do YouTube (fallback quando transcript indisponível)
"""

import os
import re
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone

import feedparser

SHOW_NOTES_MIN_CHARS  = 500
WHISPER_START_DEFAULT = 0
WHISPER_DURATION_DEFAULT = 600
WHISPER_MODEL_DEFAULT = 'base'
MAX_CONTENT_CHARS = 6000

_YOUTUBE_PATTERNS = [
    r'(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
]


# ── Detecção de URL ───────────────────────────────────────────────────────────

def _extract_youtube_id(url: str) -> str | None:
    for pattern in _YOUTUBE_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _is_youtube_url(url: str) -> bool:
    return bool(_extract_youtube_id(url))


def _is_audio_url(url: str) -> bool:
    clean = url.split('?')[0].lower()
    return any(clean.endswith(ext) for ext in ('.mp3', '.m4a', '.ogg', '.wav', '.flac', '.opus'))


# ── Utilidades ────────────────────────────────────────────────────────────────

def _clean_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _range_label(settings: dict) -> str:
    start    = int(settings.get('whisper_start', WHISPER_START_DEFAULT))
    duration = int(settings.get('whisper_duration', WHISPER_DURATION_DEFAULT))
    s_min, e_min = start // 60, (start + duration) // 60
    return f'{s_min}-{e_min} min' if start else f'primeiros {e_min} min'


# ── RSS helpers ───────────────────────────────────────────────────────────────

def _extract_enclosure(entry) -> str:
    for link in entry.get('enclosures', []):
        href = link.get('href') or link.get('url', '')
        if href:
            return href
    return entry.get('link', '')


def _get_show_notes(entry) -> str:
    for content in entry.get('content', []):
        if content.get('value'):
            return _clean_html(content['value'])
    raw = entry.get('summary', '') or entry.get('description', '')
    return _clean_html(raw)


# ── Transcrição (Whisper) ─────────────────────────────────────────────────────

def _transcribe(audio_path: str, model_name: str) -> str:
    try:
        import whisper
    except ImportError:
        print('    [aviso] whisper não instalado. pip install openai-whisper')
        return ''
    try:
        print(f'    Transcrevendo com Whisper ({model_name})...')
        model = whisper.load_model(model_name)
        result = model.transcribe(audio_path, language='pt', fp16=False)
        text = result.get('text', '').strip()
        print(f'    Transcrição: {len(text)} chars')
        return text[:MAX_CONTENT_CHARS]
    except Exception as e:
        print(f'    [aviso] Falha na transcrição: {e}')
        return ''


# ── Download e recorte (podcast MP3) ─────────────────────────────────────────

def _download_partial(audio_url: str, start_sec: int, duration_sec: int, out_path: str) -> bool:
    """Baixa o MP3 e recorta o trecho com pydub."""
    try:
        from pydub import AudioSegment
    except ImportError:
        print('    [aviso] pydub não instalado. pip install pydub')
        return False

    full_tmp = None
    try:
        print('    Baixando áudio do podcast...')
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            full_tmp = f.name
        urllib.request.urlretrieve(audio_url, full_tmp)

        audio = AudioSegment.from_file(full_tmp)
        start_ms = start_sec * 1000
        end_ms   = (start_sec + duration_sec) * 1000
        clip     = audio[start_ms : min(end_ms, len(audio))]
        clip.export(out_path, format='mp3', bitrate='64k')
        print(f'    Trecho: {start_sec}s – {start_sec + int(len(clip) / 1000)}s')
        return True
    except Exception as e:
        print(f'    [aviso] Falha ao processar áudio: {e}')
        return False
    finally:
        if full_tmp:
            try:
                os.unlink(full_tmp)
            except OSError:
                pass


# ── YouTube ───────────────────────────────────────────────────────────────────

def _yt_transcript(video_id: str) -> str:
    """Busca transcrição via youtube-transcript-api (sem download de áudio)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        for langs in (['pt', 'pt-BR'], ['en'], []):
            try:
                fetched = api.fetch(video_id, languages=langs) if langs else api.fetch(video_id)
                return ' '.join(s.text for s in fetched)[:MAX_CONTENT_CHARS]
            except Exception:
                continue
    except ImportError:
        pass
    return ''


def _yt_info(url: str) -> tuple[str, str, str]:
    """Retorna (title, description, channel) sem baixar o áudio."""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title   = info.get('title', '') or ''
            desc    = (info.get('description', '') or '')[:MAX_CONTENT_CHARS]
            channel = info.get('channel', '') or info.get('uploader', '') or ''
            return title, desc, channel
    except ImportError:
        print('    [aviso] yt-dlp não instalado. pip install yt-dlp')
    except Exception as e:
        print(f'    [aviso] Falha ao obter info do YouTube: {e}')
    return '', '', ''


def _yt_download_audio(url: str, start_sec: int, duration_sec: int, out_path: str) -> bool:
    """Baixa o áudio do YouTube com yt-dlp e recorta o trecho com pydub."""
    try:
        import yt_dlp
    except ImportError:
        print('    [aviso] yt-dlp não instalado. pip install yt-dlp')
        return False
    try:
        from pydub import AudioSegment
    except ImportError:
        print('    [aviso] pydub não instalado. pip install pydub')
        return False

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, 'audio.%(ext)s')
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': outtmpl,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '64',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            print('    Baixando áudio do YouTube...')
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Localiza o arquivo gerado
            downloaded = [f for f in os.listdir(tmpdir) if f.startswith('audio.')]
            if not downloaded:
                print('    [aviso] Arquivo de áudio não encontrado após download.')
                return False

            audio_path = os.path.join(tmpdir, downloaded[0])
            audio    = AudioSegment.from_file(audio_path)
            start_ms = start_sec * 1000
            end_ms   = (start_sec + duration_sec) * 1000
            clip     = audio[start_ms : min(end_ms, len(audio))]
            clip.export(out_path, format='mp3', bitrate='64k')
            print(f'    Trecho: {start_sec}s – {start_sec + int(len(clip) / 1000)}s')
            return True
    except Exception as e:
        print(f'    [aviso] Falha ao baixar áudio do YouTube: {e}')
        return False


def _get_content_youtube(url: str, video_id: str, settings: dict) -> tuple[str, str, str]:
    """
    Obtém (title, content, channel) de um vídeo do YouTube.
    Estratégia em cascata:
      1. Transcrição via youtube-transcript-api (sem download)
      2. Descrição do vídeo via yt-dlp info (sem download de áudio)
      3. Download de áudio com yt-dlp + transcrição Whisper
    """
    min_chars = int(settings.get('show_notes_min_chars', SHOW_NOTES_MIN_CHARS))
    start     = int(settings.get('whisper_start', WHISPER_START_DEFAULT))
    duration  = int(settings.get('whisper_duration', WHISPER_DURATION_DEFAULT))
    model     = settings.get('whisper_model', WHISPER_MODEL_DEFAULT)

    # 1. Transcrição via youtube-transcript-api
    print('    Buscando transcrição do YouTube...')
    transcript = _yt_transcript(video_id)
    if transcript:
        print(f'    Transcrição obtida ({len(transcript)} chars).')

    # Info do vídeo (título, descrição, canal) — sempre tenta, mesmo sem yt-dlp
    title, description, channel = _yt_info(url)

    if len(transcript) >= min_chars:
        content = transcript
        if description:
            content = f'[Descrição]\n{description}\n\n[Transcrição]\n{transcript}'
        return title, content, channel

    # 2. Descrição como fallback leve
    if len(description) >= min_chars:
        print(f'    Descrição suficiente ({len(description)} chars) — sem transcrição.')
        return title, description, channel

    # 3. Download de áudio + Whisper
    available = len(transcript) + len(description)
    print(f'    Conteúdo insuficiente ({available} chars) — usando Whisper...')

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        if _yt_download_audio(url, start, duration, tmp_path):
            whisper_text = _transcribe(tmp_path, model)
            if whisper_text:
                parts = []
                if description:
                    parts.append(f'[Descrição]\n{description}')
                parts.append(f'[Transcrição]\n{whisper_text}')
                return title, '\n\n'.join(parts), channel
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Usa o que tiver
    return title, transcript or description, channel


# ── Conteúdo para podcast/MP3 ─────────────────────────────────────────────────

def _get_content(audio_url: str, show_notes: str, settings: dict) -> str:
    """Estratégia híbrida para podcasts MP3: show notes se suficientes, senão Whisper."""
    min_chars = int(settings.get('show_notes_min_chars', SHOW_NOTES_MIN_CHARS))

    if len(show_notes) >= min_chars:
        print(f'    Show notes suficientes ({len(show_notes)} chars) — sem transcrição.')
        return show_notes[:MAX_CONTENT_CHARS]

    if not audio_url:
        print('    Show notes insuficientes e sem URL de áudio — usando o que há.')
        return show_notes

    start    = int(settings.get('whisper_start', WHISPER_START_DEFAULT))
    duration = int(settings.get('whisper_duration', WHISPER_DURATION_DEFAULT))
    model    = settings.get('whisper_model', WHISPER_MODEL_DEFAULT)

    print(f'    Show notes curtas ({len(show_notes)} chars) — usando Whisper...')

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        if _download_partial(audio_url, start, duration, tmp_path):
            transcript = _transcribe(tmp_path, model)
            if transcript:
                if show_notes:
                    return f'[Show notes]\n{show_notes}\n\n[Transcrição]\n{transcript}'
                return transcript
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return show_notes


# ── CLI param parser ──────────────────────────────────────────────────────────

def _parse_param(param: str) -> dict:
    """
    Parseia o parâmetro CLI.
    - URL pura:    podcast:https://...
    - chave=valor: podcast:url=https://...,start=300,duration=600,topic=IA
    """
    if not param:
        return {}
    if '=' not in param:
        return {'url': param}

    result = {}
    for part in re.split(r',(?=[a-z_]+=)', param):
        k, _, v = part.partition('=')
        result[k.strip()] = v.strip()

    if 'start' in result:
        result['whisper_start'] = result.pop('start')
    if 'duration' in result:
        result['whisper_duration'] = result.pop('duration')
    if 'model' in result:
        result['whisper_model'] = result.pop('model')

    return result


# ── fetch (entry point) ───────────────────────────────────────────────────────

def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings = dict(source_config.get('settings') or {})

    cli_param = source_config.get('_param')
    if cli_param:
        settings.update(_parse_param(cli_param))

    url           = settings.get('url', '')
    topic         = settings.get('topic', '')
    max_items     = int(settings.get('max_items', 1))
    days_lookback = int(settings.get('days_lookback', 7))

    if not url:
        print('  [podcast] Nenhuma URL configurada em settings.url')
        return []

    items = []

    if _is_youtube_url(url):
        video_id = _extract_youtube_id(url)
        print(f'  [podcast/youtube] {url}')
        title, content, channel = _get_content_youtube(url, video_id, settings)
        if content:
            title = title or 'Vídeo do YouTube'
            items.append(_make_item(title, url, url, content,
                                    source_config, topic, settings, channel=channel))

    elif _is_audio_url(url):
        title = os.path.basename(url.split('?')[0]) or 'Episódio'
        print(f'  [podcast] {title[:70]}')
        content = _get_content(url, '', settings)
        if content:
            items.append(_make_item(title, url, url, content, source_config, topic, settings))

    else:
        # RSS feed
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        feed = feedparser.parse(url)
        podcast_name = feed.feed.get('title', source_config.get('name', 'Podcast'))

        count = 0
        for entry in feed.entries:
            if count >= max_items:
                break

            pub_parsed = entry.get('published_parsed') or entry.get('updated_parsed')
            if pub_parsed:
                pub_dt = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue

            title     = entry.get('title', '').strip()
            audio_url = _extract_enclosure(entry)
            notes     = _get_show_notes(entry)
            ep_url    = entry.get('link', audio_url or url)

            print(f'  [{podcast_name}] {title[:70]}')
            content = _get_content(audio_url, notes, settings)

            if content:
                items.append(_make_item(title, ep_url, audio_url, content,
                                        source_config, topic, settings,
                                        channel=podcast_name, pub_parsed=pub_parsed))
                count += 1

    return items


def _make_item(title: str, url: str, audio_url: str, content: str,
               source_config: dict, topic: str, settings: dict,
               channel: str = '', pub_parsed=None) -> dict:
    source_name = source_config.get('name', channel or 'Podcast')
    pub_dt = (datetime(*pub_parsed[:6], tzinfo=timezone.utc)
              if pub_parsed else datetime.now(timezone.utc))

    return {
        'id':           audio_url or url,
        'title':        title,
        'url':          url,
        'text':         content,
        'source_name':  source_name,
        'source_type':  'podcast',
        'published_at': pub_dt.isoformat(),
        'channel':      channel or source_name,
        'views':        0,
        'comments':     [],
        'topic':        topic,
        'range_label':  _range_label(settings),
    }
