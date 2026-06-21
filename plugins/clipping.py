"""
Plugin RadioIA — Clipping de Mídia

Busca como diferentes veículos estão cobrindo um tema específico e gera
um episódio no estilo "o que a imprensa diz sobre X".

Uso:
  python main.py "clipping:queda de avião da empresa xyz"
  python main.py "clipping:eleições municipais 2026"

O tópico é sempre passado via CLI — o config.yaml define apenas os defaults.

Para usar, adicione ao config.yaml:
  - id: clipping
    type: clipping
    name: "Clipping"
    enabled: true
    settings:
      max_sources: 5        # máximo de veículos a incluir
      days_lookback: 1      # só artigos dos últimos N dias
      fetch_content: true   # extrai texto completo via trafilatura (recomendado)
      max_content_chars: 2000
      agregadores:          # ordem não implica prioridade — seleção é balanceada
        - google_news
        - bing_news
"""

import hashlib
import re
import urllib.parse
from datetime import date, timedelta
from itertools import zip_longest

import feedparser
import trafilatura

GOOGLE_NEWS_RSS   = "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
BING_NEWS_RSS     = "https://www.bing.com/news/search?q={query}&format=RSS&mkt=pt-BR&cc=BR&freshness={freshness}"
MAX_CONTENT_CHARS = 2000
RSS_FETCH_LIMIT   = 20   # máximo de entradas a processar do RSS por agregador


# ── Funções de URL por agregador ──────────────────────────────────────────────

def _google_news_url(topic: str, followup: bool, days_lookback: int) -> str:
    query = topic
    if followup:
        since = (date.today() - timedelta(days=max(1, days_lookback))).isoformat()
        query = f'{topic} after:{since}'
    return GOOGLE_NEWS_RSS.format(query=urllib.parse.quote(query))


def _bing_news_url(topic: str, followup: bool, days_lookback: int) -> str:
    freshness = 'Day' if days_lookback <= 1 else ('Week' if days_lookback <= 7 else 'Month')
    return BING_NEWS_RSS.format(query=urllib.parse.quote(topic), freshness=freshness)


AGGREGATORS: dict[str, callable] = {
    'google_news': _google_news_url,
    'bing_news':   _bing_news_url,
}

DEFAULT_AGGREGATORS = ['google_news', 'bing_news']


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pub_date(entry) -> date | None:
    try:
        import email.utils
        return email.utils.parsedate_to_datetime(entry.get('published', '')).date()
    except Exception:
        return None


def _source_name(entry) -> str:
    name = (entry.get('source') or {}).get('title', '')
    if name:
        return name
    title = entry.get('title', '')
    if ' - ' in title:
        return title.rsplit(' - ', 1)[-1].strip()
    return 'Fonte desconhecida'


def _resolve_url(url: str) -> str:
    """Segue redirects HTTP e retorna a URL final do artigo original."""
    import requests
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10,
                             headers={'User-Agent': 'Mozilla/5.0'})
        final = resp.url
        # Descarta se ainda estiver em domínio de agregador (redirect não resolvido)
        if 'google.com' in final or 'bing.com' in final:
            return url
        return final
    except Exception:
        return url


def _fetch_content(url: str, max_chars: int) -> tuple[str, str, str]:
    """Retorna (título, texto, url_final)."""
    final_url = _resolve_url(url)
    try:
        downloaded = trafilatura.fetch_url(final_url)
        if not downloaded:
            return '', '', final_url
        text  = trafilatura.extract(downloaded, include_comments=False,
                                    include_tables=False, no_fallback=False) or ''
        meta  = trafilatura.extract_metadata(downloaded)
        title = (meta.title if meta else '') or ''
        return title, text[:max_chars], final_url
    except Exception:
        return '', '', final_url


def _rss_summary(entry) -> str:
    raw = entry.get('summary', '')
    return re.sub(r'<[^>]+>', '', raw).strip()


def _fetch_entries(url: str, since: date, max_entries: int,
                   seen_urls: set, fetch_full: bool, max_chars: int,
                   topic: str, source_config: dict) -> list[dict]:
    """Processa entradas de um RSS e retorna items no formato padrão."""
    feed  = feedparser.parse(url)
    items = []
    today = date.today().isoformat()

    for entry in feed.entries[:max_entries]:
        pub = _pub_date(entry)
        if pub and pub < since:
            continue

        entry_url = entry.get('link', '').strip()
        if not entry_url or entry_url in seen_urls:
            continue
        seen_urls.add(entry_url)

        source      = _source_name(entry)
        rss_title   = entry.get('title', source)
        clean_title = rss_title
        if rss_title.endswith(f' - {source}'):
            clean_title = rss_title[: -(len(source) + 3)].strip()

        print(f'  [{source}] {clean_title[:65]}...' if len(clean_title) > 65 else f'  [{source}] {clean_title}')

        text      = ''
        title     = clean_title
        final_url = entry_url
        if fetch_full:
            fetched_title, fetched_text, canonical = _fetch_content(entry_url, max_chars)
            if fetched_text:
                text = fetched_text
            if fetched_title:
                title = fetched_title
            if canonical:
                final_url = canonical
        if not text:
            text = _rss_summary(entry)
        if not text:
            continue

        uid = hashlib.md5(entry_url.encode()).hexdigest()[:8]
        items.append({
            'id':           f'clipping-{uid}-{today}',
            'title':        title,
            'url':          final_url,
            'text':         text,
            'source_name':  source,
            'source_type':  source_config.get('type', 'clipping'),
            'published_at': pub.isoformat() if pub else today,
            'views':        0,
            'comments':     [],
            'channel':      topic,
        })

    return items


def _interleave_balanced(lists: list[list]) -> list:
    """
    Round-robin entre listas: pega 1 item de cada por vez, sem prioridade fixa.
    Se uma lista esgotar, continua com as demais.

    Exemplo com 3 listas [A1,A2,A3], [B1,B2], [C1]:
    → C1, B1, A1, B2, A2, A3
    """
    sentinel = object()
    result   = []
    for group in zip_longest(*lists, fillvalue=sentinel):
        for item in group:
            if item is not sentinel:
                result.append(item)
    return result


def _dedup_by_source(items: list[dict]) -> list[dict]:
    """Remove duplicatas do mesmo veículo, mantendo o primeiro encontrado."""
    seen   = set()
    result = []
    for item in items:
        key = item['source_name'].strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings      = source_config.get('settings') or {}
    topic         = settings.get('topic', '').strip()
    days_lookback = int(settings.get('days_lookback', 1))
    fetch_full    = settings.get('fetch_content', True)
    max_chars     = int(settings.get('max_content_chars', MAX_CONTENT_CHARS))
    followup      = bool(settings.get('followup', False))
    max_sources   = int(settings.get('max_sources', 5))
    agregadores   = settings.get('agregadores', DEFAULT_AGGREGATORS)

    if not topic:
        print('  [clipping] nenhum tópico informado. Use: python main.py "clipping:seu tópico"')
        return []

    unknown = [a for a in agregadores if a not in AGGREGATORS]
    if unknown:
        print(f'  [clipping] agregadores desconhecidos ignorados: {unknown}. Disponíveis: {list(AGGREGATORS)}')
    agregadores = [a for a in agregadores if a in AGGREGATORS]
    if not agregadores:
        return []

    mode = 'followup' if followup else 'primeira cobertura'

    # Janelas de busca: tenta lookback configurado; se 0 resultados, amplia progressivamente
    fallback_windows = [days_lookback] if followup else sorted(set([days_lookback, 7, 30]))

    merged: list[dict] = []
    used_window = days_lookback
    for window in fallback_windows:
        if window != days_lookback:
            print(f'  Sem resultados — ampliando busca para os últimos {window} dias...')

        print(f'  Buscando cobertura [{mode}]: "{topic}" via {", ".join(agregadores)}')
        since     = date.today() - timedelta(days=window)
        seen_urls: set = set()

        per_agg = []
        for agg_name in agregadores:
            url   = AGGREGATORS[agg_name](topic, followup, window)
            items = _fetch_entries(url, since, RSS_FETCH_LIMIT, seen_urls,
                                   fetch_full, max_chars, topic, source_config)
            per_agg.append(items)
            print(f'  {agg_name}: {len(items)} resultado(s)')

        merged = _interleave_balanced(per_agg)
        used_window = window
        if merged:
            break

    if not merged:
        print(f'  {len(merged)} veículo(s) selecionado(s) sobre "{topic}".')
        return []

    if used_window != days_lookback:
        print(f'  (resultados encontrados com janela de {used_window} dias)')

    # Remove segundo artigo do mesmo veículo (perspectivas distintas é o objetivo)
    deduped = _dedup_by_source(merged)

    result = deduped[:max_sources]
    print(f'  {len(result)} veículo(s) selecionado(s) sobre "{topic}".')
    return result
