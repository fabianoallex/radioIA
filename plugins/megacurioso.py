"""
Mega Curioso plugin para RadioIA

Busca artigos do feed do Mega Curioso e gera episódios de curiosidades.
O conteúdo completo já vem no campo content:encoded do feed, sem precisar
visitar cada URL de artigo.

A API do Mega Curioso aceita o número de artigos diretamente na URL:
  https://strapi.megacurioso.com.br/api/feed/{max_items}

O plugin constrói essa URL automaticamente com base em max_items.

Para usar, adicione ao config.yaml:
  - id: megacurioso
    type: megacurioso
    name: "Mega Curioso"
    enabled: true
    settings:
      feed_base_url: https://strapi.megacurioso.com.br/api/feed
      fetch_count: 10       # quantos artigos buscar da API (pool)
      max_items: 1          # quantos artigos usar por episodio (apos filtro de historico)
      days_lookback: 7      # ignora artigos mais antigos que N dias
      max_content_chars: 3000
"""

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

FEED_BASE_URL_DEFAULT = 'https://strapi.megacurioso.com.br/api/feed'
MAX_CONTENT_CHARS = 3000

METADATA = {
    'name':        'Mega Curioso',
    'description': 'Curiosidades e ciência do Mega Curioso',
    'icon':        'star',
    'credentials': [],
    'config_schema': [
        {
            'key': 'feed_base_url', 'label': 'URL base do feed', 'type': 'text',
            'default': FEED_BASE_URL_DEFAULT,
        },
        {'key': 'fetch_count',      'label': 'Artigos a buscar (pool)', 'type': 'number', 'default': 10},
        {'key': 'max_items',        'label': 'Artigos por episódio',    'type': 'number', 'default': 1},
        {'key': 'days_lookback',    'label': 'Dias de lookback',        'type': 'number', 'default': 7},
        {'key': 'max_content_chars','label': 'Máx. caracteres',         'type': 'number', 'default': MAX_CONTENT_CHARS},
    ],
}


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'figure', 'figcaption', 'img']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return re.sub(r'\s+', ' ', text).strip()


def _parse_date(entry) -> datetime | None:
    for field in ('published', 'updated'):
        val = entry.get(field)
        if val:
            try:
                return parsedate_to_datetime(val).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    parsed = entry.get('published_parsed') or entry.get('updated_parsed')
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def _get_content(entry) -> str:
    # content:encoded → feedparser expõe como entry.content list
    if entry.get('content'):
        for block in entry.content:
            if block.get('value'):
                return block['value']
    # fallback: summary (pode ser HTML resumido)
    return entry.get('summary', '')


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings      = source_config.get('settings') or {}
    feed_base_url = settings.get('feed_base_url', FEED_BASE_URL_DEFAULT).rstrip('/')
    fetch_count   = int(settings.get('fetch_count', 10))
    days_lookback = int(settings.get('days_lookback', 7))
    max_chars     = int(settings.get('max_content_chars', MAX_CONTENT_CHARS))
    source_name   = source_config.get('name', 'Mega Curioso')

    # a API aceita o limite de artigos diretamente na URL: /api/feed/{n}
    # fetch_count define o pool; main.py aplica max_items apos filtrar historico
    feed_url = f'{feed_base_url}/{fetch_count}'

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)

    try:
        resp = requests.get(
            feed_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadioIA/1.0)'},
            timeout=15,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f'  [megacurioso] Erro ao buscar feed: {e}')
        return []

    if not feed.entries:
        print('  [megacurioso] Feed sem entradas')
        return []

    items = []
    for entry in feed.entries:
        if len(items) >= max_items:
            break

        url   = entry.get('link', '').strip()
        title = entry.get('title', '').strip()
        if not url or not title:
            continue

        published = _parse_date(entry)
        if published and published < cutoff:
            continue

        html_content = _get_content(entry)
        text = _html_to_text(html_content)[:max_chars] if html_content else ''
        if not text:
            print(f'  [megacurioso] Sem conteúdo: {title[:60]}')
            continue

        category = ''
        if entry.get('tags'):
            category = entry.tags[0].get('term', '')

        pub_iso = (published or datetime.now(timezone.utc)).isoformat()

        items.append({
            'id':           url,
            'title':        title,
            'url':          url,
            'text':         text,
            'source_name':  source_name,
            'source_type':  'rss',
            'published_at': pub_iso,
            'views':        0,
            'comments':     [],
            'channel':      category or source_name,
        })
        print(f'  [megacurioso] {title[:70]}')

    return items
