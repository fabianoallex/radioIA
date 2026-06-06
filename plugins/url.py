import trafilatura
from datetime import date

MAX_CONTENT_CHARS = 3000


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings = source_config.get('settings') or {}
    url      = settings.get('url', '').strip()

    if not url:
        return []

    today = date.today().isoformat()
    print(f"  Buscando: {url}")

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            print(f"  [url] Não foi possível acessar: {url}")
            return []

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        ) or ''

        if not text:
            print(f"  [url] Sem conteúdo extraído de: {url}")
            return []

        meta  = trafilatura.extract_metadata(downloaded)
        title = (meta.title if meta else '') or url

        print(f"  Título: {title[:70]}")

        return [{
            'id':           f"url-{abs(hash(url)) % 10**8}-{today}",
            'title':        title,
            'url':          url,
            'text':         text[:MAX_CONTENT_CHARS],
            'source_name':  'Conteúdo da Web',
            'source_type':  'url',
            'published_at': today,
            'views':        0,
            'comments':     [],
            'channel':      '',
        }]

    except Exception as e:
        print(f"  [url] Erro: {e}")
        return []
