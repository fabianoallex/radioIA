from datetime import datetime, timedelta, timezone
import json
import random
from urllib.parse import urljoin, urlparse

import feedparser
from lxml import html as lxml_html
import trafilatura

MAX_ARTICLE_CHARS = 1200


def _parse_date(entry) -> datetime | None:
    parsed = entry.get('published_parsed') or entry.get('updated_parsed')
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
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
        downloaded = trafilatura.fetch_url(url)
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


def _scrape_page_links(page_url: str) -> list[str]:
    """Extrai URLs de artigos de uma página sem RSS nativo."""
    downloaded = trafilatura.fetch_url(page_url)
    if not downloaded:
        return []
    try:
        base = urlparse(page_url)
        tree = lxml_html.fromstring(downloaded)
        seen: set[str] = set()
        links: list[str] = []
        for a in tree.xpath('//a[@href]'):
            href = urljoin(page_url, a.get('href', '').strip())
            parsed = urlparse(href)
            if (parsed.netloc == base.netloc
                    and parsed.path not in ('', '/')
                    and href not in seen):
                seen.add(href)
                links.append(href)
        return links
    except Exception:
        return []


def fetch(source_config: dict, credentials=None) -> list[dict]:
    feeds = source_config.get('feeds', [])
    settings = source_config.get('settings', {})
    max_per_feed = settings.get('max_items_per_feed', 3)
    max_total = settings.get('max_items_total', 10)
    days_lookback = settings.get('days_lookback', 1)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)

    feeds = random.sample(feeds, len(feeds))
    all_items = []

    for feed_config in feeds:
        if len(all_items) >= max_total:
            break

        feed_name = feed_config.get('name', '')

        if feed_config.get('scrape'):
            if not feed_name:
                feed_name = feed_config['url']
            count = 0
            for link in _scrape_page_links(feed_config['url']):
                if count >= max_per_feed or len(all_items) >= max_total:
                    break
                title, text, published = _extract_article(link)
                if not title or not text:
                    continue
                if published and published < cutoff:
                    continue
                all_items.append({
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
                count += 1
                print(f"  [{feed_name}] {title[:70]}")

        else:
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
