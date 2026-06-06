import html
import re
from datetime import date
from urllib.parse import quote

import feedparser
import trafilatura

MAX_CHARS = 800

SIGN_PAIRS = [
    ('aries',        'touro'),
    ('gemeos',       'cancer'),
    ('leao',         'virgem'),
    ('libra',        'escorpiao'),
    ('sagitario',    'capricornio'),
    ('aquario',      'peixes'),
]

SIGN_PT = {
    'aries':       'Áries',
    'touro':       'Touro',
    'gemeos':      'Gêmeos',
    'cancer':      'Câncer',
    'leao':        'Leão',
    'virgem':      'Virgem',
    'libra':       'Libra',
    'escorpiao':   'Escorpião',
    'sagitario':   'Sagitário',
    'capricornio': 'Capricórnio',
    'aquario':     'Aquário',
    'peixes':      'Peixes',
}


def _today_pair(pair_index: int | None = None) -> tuple[str, str]:
    idx = pair_index if pair_index is not None else (date.today().timetuple().tm_yday % 6)
    return SIGN_PAIRS[idx]


def _clean(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:MAX_CHARS]


def _extract_url(url: str) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(downloaded, include_comments=False,
                                            include_tables=False, no_fallback=False)
            return _clean(extracted or '')
    except Exception:
        pass
    return ''


def _fetch_sign(sign: str, sign_name: str) -> dict | None:
    today = date.today().isoformat()

    # 1. Tenta Personare (conteúdo por signo específico)
    personare_url = f'https://www.personare.com.br/horoscopo-do-dia/{sign}'
    text = _extract_url(personare_url)
    if len(text) > 200:
        print(f"  [{sign_name}] Personare ({len(text)} chars)")
        return _make_item(sign, sign_name, today, personare_url, text)

    # 2. Fallback: Google News — pega o artigo mais completo dos 5 primeiros
    query = quote(f'horóscopo {sign_name} hoje')
    url   = f'https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419'
    feed  = feedparser.parse(url)
    best_text, best_link, best_title = '', '', ''

    for entry in feed.entries[:5]:
        link  = entry.get('link', '')
        title = entry.get('title', '')
        t = _extract_url(link) or _clean(entry.get('summary', ''))
        if len(t) > len(best_text):
            best_text, best_link, best_title = t, link, title

    if best_text:
        print(f"  [{sign_name}] {best_title[:65]} ({len(best_text)} chars)")
        return _make_item(sign, sign_name, today, best_link, best_text)

    return None


def _make_item(sign: str, sign_name: str, today: str, url: str, text: str) -> dict:
    return {
        'id':           f"horoscopo-{sign}-{today}",
        'title':        f"Horóscopo de {sign_name}",
        'url':          url,
        'text':         text,
        'source_name':  sign_name,
        'source_type':  'horoscopo',
        'published_at': today,
        'views':        0,
        'comments':     [],
        'channel':      sign_name,
    }


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings   = source_config.get('settings') or {}
    pair_index = settings.get('pair_index')  # None = auto-rotação por data

    sign_a, sign_b = _today_pair(pair_index)
    name_a = SIGN_PT[sign_a]
    name_b = SIGN_PT[sign_b]

    print(f"  Signos de hoje: {name_a} e {name_b}")

    items = []
    for sign, name in [(sign_a, name_a), (sign_b, name_b)]:
        item = _fetch_sign(sign, name)
        if item:
            items.append(item)

    return items
