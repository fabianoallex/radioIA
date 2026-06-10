import re
import trafilatura
from datetime import date

MAX_CONTENT_CHARS_DEFAULT = 3000

_YT_DOMAINS = ('youtube.com/watch', 'youtu.be/', 'youtube.com/shorts/')
_YT_ID_RE   = re.compile(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})')


def _youtube_video_id(url: str) -> str | None:
    if not any(d in url for d in _YT_DOMAINS):
        return None
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def _fetch_youtube(video_id: str, url: str, max_chars: int) -> tuple[str, str, str, str]:
    """Retorna (title, text, sitename, published_at)."""
    text = ''
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=['pt', 'en'])
        except Exception:
            fetched = api.fetch(video_id)
        text = ' '.join(s.text for s in fetched)[:max_chars]
    except Exception as e:
        print(f"  [url] YouTube sem transcrição: {e}")

    title    = f'Vídeo do YouTube ({video_id})'
    pub_date = date.today().isoformat()
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            meta = trafilatura.extract_metadata(downloaded)
            if meta:
                if meta.title:
                    title = meta.title
                if meta.date:
                    pub_date = meta.date
    except Exception:
        pass

    return title, text, 'YouTube', pub_date


def _fetch_web(url: str, max_chars: int) -> tuple[str, str, str, str]:
    """Retorna (title, text, sitename, published_at)."""
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return '', '', '', ''

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    ) or ''

    meta     = trafilatura.extract_metadata(downloaded)
    title    = (meta.title    if meta else '') or url
    sitename = (meta.sitename if meta else '') or 'Conteúdo da Web'
    pub_date = (meta.date     if meta else '') or date.today().isoformat()

    return title, text[:max_chars], sitename, pub_date


def fetch(source_config: dict, credentials=None) -> list[dict]:
    """
    Gera itens a partir de uma ou mais URLs.

    source_config['settings']:
        url            — URL única ou várias separadas por vírgula
        context        — instrução extra para o roteirista (ex: "foca nos impactos econômicos")
        max_content_chars — limite de caracteres por URL (padrão: 3000)

    Formatos suportados via CLI/MCP:
        url:https://exemplo.com
        url:https://exemplo.com|foca nos aspectos técnicos
        url:https://a.com,https://b.com|compare as duas matérias
        url:https://youtube.com/watch?v=ID   (usa transcrição automática)
    """
    settings  = source_config.get('settings') or {}
    raw_url   = settings.get('url', '').strip()
    max_chars = int(settings.get('max_content_chars', MAX_CONTENT_CHARS_DEFAULT))
    today     = date.today().isoformat()

    urls = [u.strip() for u in raw_url.split(',') if u.strip()]
    if not urls:
        return []

    items = []
    for url in urls:
        print(f"  Buscando: {url}")
        video_id = _youtube_video_id(url)
        try:
            if video_id:
                title, text, sitename, pub_date = _fetch_youtube(video_id, url, max_chars)
            else:
                title, text, sitename, pub_date = _fetch_web(url, max_chars)
        except Exception as e:
            print(f"  [url] Erro: {e}")
            continue

        if not text:
            print(f"  [url] Sem conteúdo extraído de: {url}")
            continue

        print(f"  [{sitename}] {title[:70]}")
        items.append({
            'id':           f"url-{abs(hash(url)) % 10**8}-{today}",
            'title':        title,
            'url':          url,
            'text':         text,
            'source_name':  sitename,
            'source_type':  'url',
            'published_at': pub_date,
            'views':        0,
            'comments':     [],
            'channel':      sitename,
        })

    return items
