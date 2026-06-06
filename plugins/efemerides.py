import datetime
import requests

WIKI_API = 'https://pt.wikipedia.org/api/rest_v1/feed/onthisday'

CATEGORY_LABELS = {
    'selected': 'Efemérides',
    'events':   'Eventos',
    'births':   'Nascimentos',
    'deaths':   'Falecimentos',
}


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings   = source_config.get('settings', {})
    max_events = settings.get('max_events', 5)
    categories = settings.get('categories', ['selected', 'events'])

    today = datetime.date.today()
    month = today.strftime('%m')
    day   = today.strftime('%d')

    try:
        resp = requests.get(
            f"{WIKI_API}/all/{month}/{day}",
            timeout=10,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'RadioIA/1.0 (radio pessoal; contato: usuario)',
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [efemerides] Erro ao buscar Wikipedia: {e}")
        return []

    items      = []
    seen_texts = set()
    date_key   = today.strftime('%m%d')

    for cat in categories:
        for event in data.get(cat, []):
            if len(items) >= max_events:
                break

            text = event.get('text', '').strip()
            year = event.get('year', '')
            if not text or text in seen_texts:
                continue
            seen_texts.add(text)

            pages   = event.get('pages', [])
            page    = pages[0] if pages else {}
            url     = page.get('content_urls', {}).get('desktop', {}).get('page', '')
            extract = page.get('extract', '')

            items.append({
                'id':          f"efemeride-{date_key}-{year}-{abs(hash(text))}",
                'title':       f"{year} — {text}",
                'url':         url,
                'text':        (extract[:800] if extract else text),
                'source_name': CATEGORY_LABELS.get(cat, cat),
                'source_type': 'efemerides',
                'published_at': today.isoformat(),
                'views':       0,
                'comments':    [],
                'channel':     'Wikipedia',
            })

            print(f"  [{year}] {text[:70]}")

        if len(items) >= max_events:
            break

    return items[:max_events]
