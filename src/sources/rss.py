from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import random
from urllib.parse import urljoin, urlparse

import feedparser
from lxml import html as lxml_html
import requests as _requests
import trafilatura

MAX_ARTICLE_CHARS = 1200
MAX_SCRAPE_CANDIDATES = 20
_HTTP_TIMEOUT = 10
_HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}


def _parse_date(entry) -> datetime | None:
    parsed = entry.get('published_parsed') or entry.get('updated_parsed')
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def _fetch_html(url: str) -> str | None:
    try:
        r = _requests.get(url, timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS, verify=True)
        if r.status_code < 400:
            return r.text
    except _requests.exceptions.SSLError:
        try:
            r = _requests.get(url, timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS, verify=False)
            if r.status_code < 400:
                return r.text
        except Exception:
            pass
    except Exception:
        pass
    return None


def _extract_text(url: str) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False
            )
            return (text or '')[:MAX_ARTICLE_CHARS]
    except Exception:
        pass
    return ''


def _extract_article(url: str) -> tuple[str, str, datetime | None]:
    """Extrai título, texto e data de um artigo via trafilatura (usado no path scrape)."""
    try:
        downloaded = _fetch_html(url)
        if not downloaded:
            return '', '', None
        result = trafilatura.extract(
            downloaded,
            output_format='json',
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if result:
            data = json.loads(result)
            title = (data.get('title') or '').strip()
            text = (data.get('text') or '')[:MAX_ARTICLE_CHARS]
            date_str = data.get('date')
            date = None
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                except Exception:
                    pass
            return title, text, date
    except Exception:
        pass
    return '', '', None


def _looks_like_article(path: str) -> bool:
    """Heurística: paths com 2+ segmentos têm mais chance de ser artigos que categorias."""
    parts = [p for p in path.strip('/').split('/') if p]
    return len(parts) >= 2


def _scrape_page_links(page_url: str) -> list[str]:
    """Extrai até MAX_SCRAPE_CANDIDATES URLs de artigos de uma página sem RSS nativo.

    Prioriza links com 2+ segmentos de path (artigos) sobre links de categoria/navegação.
    """
    downloaded = _fetch_html(page_url)
    if not downloaded:
        return []
    try:
        base = urlparse(page_url)
        tree = lxml_html.fromstring(downloaded)
        seen: set[str] = set()
        article_links: list[str] = []
        fallback_links: list[str] = []

        for a in tree.xpath('//a[@href]'):
            href = urljoin(page_url, a.get('href', '').strip())
            parsed = urlparse(href)
            if (parsed.netloc != base.netloc
                    or parsed.path in ('', '/')
                    or href in seen):
                continue
            seen.add(href)
            if _looks_like_article(parsed.path):
                article_links.append(href)
            else:
                fallback_links.append(href)

        combined = article_links + fallback_links
        return combined[:MAX_SCRAPE_CANDIDATES]
    except Exception:
        return []


def _find_rss_in_html(html: str, base_url: str) -> str | None:
    """Procura feed RSS/Atom declarado no <head> da página via <link rel=alternate>."""
    try:
        tree = lxml_html.fromstring(html)
        for link in tree.xpath('//link[@rel="alternate"]'):
            mime = link.get('type', '')
            if 'rss' in mime or 'atom' in mime:
                href = link.get('href', '').strip()
                if href:
                    return urljoin(base_url, href)
    except Exception:
        pass
    return None


def _items_from_rss_url(rss_url: str, feed_name: str, max_per_feed: int, cutoff: datetime) -> list[dict]:
    """Extrai itens de uma URL RSS (usado após auto-descoberta em sites com scrape: true)."""
    try:
        feed = feedparser.parse(rss_url)
        items = []
        for entry in feed.entries:
            if len(items) >= max_per_feed:
                break
            published = _parse_date(entry)
            if published and published < cutoff:
                continue
            url = entry.get('link', '')
            title = entry.get('title', '').strip()
            if not url or not title:
                continue
            summary = entry.get('summary', '')
            text = _extract_text(url) or summary[:MAX_ARTICLE_CHARS]
            items.append({
                'id': url,
                'title': title,
                'url': url,
                'text': text,
                'source_name': feed_name,
                'source_type': 'news',
                'published_at': (published or datetime.now(timezone.utc)).isoformat(),
                'views': 0,
                'comments': [],
                'channel': feed_name,
            })
            print(f"  [{feed_name}] {title[:70]}")
        return items
    except Exception:
        return []


def _fetch_scrape_items(feed_config: dict, max_per_feed: int, cutoff: datetime) -> list[dict]:
    """Coleta itens de uma fonte com scrape: true (chamado em paralelo por fetch()).

    Estratégia: tenta auto-descoberta de RSS no <head> primeiro; se falhar, faz
    scraping de links HTML artigo por artigo.
    """
    feed_name = feed_config.get('name') or feed_config['url']
    page_url = feed_config['url']

    html = _fetch_html(page_url)
    if not html:
        print(f"  [{feed_name}] 0 itens (homepage inacessível)")
        return []

    # 1. RSS auto-descoberta — muitos sites JS-rendered ainda publicam RSS no backend
    rss_url = _find_rss_in_html(html, page_url)
    if rss_url:
        items = _items_from_rss_url(rss_url, feed_name, max_per_feed, cutoff)
        if items:
            print(f"  [{feed_name}] via RSS ({rss_url})")
            return items

    # 2. Fallback: extrai links do HTML e scrape artigo por artigo
    candidates = _scrape_page_links(page_url)
    tried = 0
    items = []
    for link in candidates:
        if len(items) >= max_per_feed:
            break
        tried += 1
        title, text, published = _extract_article(link)
        if not title or not text:
            continue
        if published and published < cutoff:
            continue
        items.append({
            'id': link,
            'title': title,
            'url': link,
            'text': text,
            'source_name': feed_name,
            'source_type': 'news',
            'published_at': (published or datetime.now(timezone.utc)).isoformat(),
            'views': 0,
            'comments': [],
            'channel': feed_name,
        })
        print(f"  [{feed_name}] {title[:70]}")

    if not items:
        detail = f"RSS descoberto mas sem itens novos: {rss_url}" if rss_url \
            else f"{len(candidates)} candidatos, {tried} tentados"
        print(f"  [{feed_name}] 0 itens ({detail})")
    return items


def fetch(source_config: dict, credentials=None) -> list[dict]:
    feeds = source_config.get('feeds', [])
    settings = source_config.get('settings', {})
    max_per_feed = settings.get('max_items_per_feed', 3)
    max_total = settings.get('max_items_total', 10)
    days_lookback = settings.get('days_lookback', 1)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)

    shuffled = random.sample(feeds, len(feeds))
    scrape_feeds = [f for f in shuffled if f.get('scrape')]
    rss_feeds = [f for f in shuffled if not f.get('scrape')]

    all_items: list[dict] = []

    # fontes scrape rodam em paralelo (IO-bound)
    if scrape_feeds:
        workers = min(4, len(scrape_feeds))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_fetch_scrape_items, f, max_per_feed, cutoff)
                for f in scrape_feeds
            ]
            for future in as_completed(futures):
                try:
                    all_items.extend(future.result())
                except Exception:
                    pass
        all_items = all_items[:max_total]

    # fontes RSS nativas rodam sequencialmente
    for feed_config in rss_feeds:
        if len(all_items) >= max_total:
            break

        feed_name = feed_config.get('name', '')
        feed = feedparser.parse(feed_config['url'])
        if not feed_name:
            feed_name = feed.feed.get('title', 'Feed')
        count = 0

        for entry in feed.entries:
            if count >= max_per_feed or len(all_items) >= max_total:
                break
            published = _parse_date(entry)
            if published and published < cutoff:
                continue
            url = entry.get('link', '')
            title = entry.get('title', '').strip()
            if not url or not title:
                continue
            summary = entry.get('summary', '')
            text = _extract_text(url) or summary[:MAX_ARTICLE_CHARS]
            all_items.append({
                'id': url,
                'title': title,
                'url': url,
                'text': text,
                'source_name': feed_name,
                'source_type': 'news',
                'published_at': (published or datetime.now(timezone.utc)).isoformat(),
                'views': 0,
                'comments': [],
                'channel': feed_name,
            })
            count += 1
            print(f"  [{feed_name}] {title[:70]}")

    return all_items
