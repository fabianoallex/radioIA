"""
Plugin: Notícias de Concursos Públicos — PCI Concursos
Fonte: https://www.pciconcursos.com.br/noticias/

Configuração no config.yaml:

  - id: concursos
    type: concursos_pci
    name: "Concursos Públicos"
    enabled: true
    settings:
      max_items: 8
      days_lookback: 2
"""

import re
from datetime import datetime, timedelta

import requests
import trafilatura

BASE_URL    = 'https://www.pciconcursos.com.br'
LISTING_URL = f'{BASE_URL}/noticias/'
HEADERS     = {'User-Agent': 'Mozilla/5.0 (compatible; RadioIA/1.0)'}


def _parse_date(text: str):
    """'05/06/2026' → date ou None."""
    try:
        return datetime.strptime(text.strip(), '%d/%m/%Y').date()
    except ValueError:
        return None


def _to_iso(d) -> str:
    return d.strftime('%Y-%m-%dT00:00:00+00:00') if d else ''


def _article_id(url: str) -> str:
    slug = url.rstrip('/').split('/')[-1]
    return 'pci-' + re.sub(r'[^a-z0-9]+', '-', slug.lower()).strip('-')


def _fetch_text(url: str) -> str:
    from src.text_utils import normalize_for_tts
    try:
        html = trafilatura.fetch_url(url)
        if html:
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
            ) or ''
            return normalize_for_tts(text)
    except Exception:
        pass
    return ''


def fetch(source_config: dict, credentials=None) -> list[dict]:
    from bs4 import BeautifulSoup

    settings      = source_config.get('settings') or {}
    max_items     = settings.get('max_items', 8)
    days_lookback = settings.get('days_lookback', 2)
    cutoff        = datetime.now().date() - timedelta(days=days_lookback)

    # ── Busca a página de listagem ────────────────────────────────────────────
    try:
        resp = requests.get(LISTING_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f'  [pci] erro ao buscar listagem: {e}')
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Estrutura: <h2>DD/MM/YYYY</h2> <ul><li><a>...</a></li>...</ul>
    entries = []  # [(date, title, url)]
    for h2 in soup.find_all('h2'):
        pub_date = _parse_date(h2.get_text())
        if not pub_date:
            continue
        if pub_date < cutoff:
            break  # lista está em ordem decrescente

        ul = h2.find_next_sibling('ul')
        if not ul:
            continue

        for li in ul.find_all('li'):
            a = li.find('a', href=True)
            if not a:
                continue
            href = a['href']
            if not href.startswith('http'):
                href = BASE_URL + href
            if '/noticias/' not in href:
                continue
            entries.append((pub_date, a.get_text(strip=True), href))
            if len(entries) >= max_items:
                break

        if len(entries) >= max_items:
            break

    if not entries:
        return []

    # ── Extrai conteúdo de cada artigo ────────────────────────────────────────
    items = []
    for pub_date, title, url in entries:
        text = _fetch_text(url)
        items.append({
            'id':           _article_id(url),
            'title':        title,
            'url':          url,
            'text':         text[:3000],
            'source_name':  'PCI Concursos',
            'source_type':  'concursos_pci',
            'published_at': _to_iso(pub_date),
            'views':        0,
            'comments':     [],
            'channel':      'Concursos Públicos',
        })

    return items
