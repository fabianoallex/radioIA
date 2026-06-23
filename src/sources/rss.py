from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import html as _html_mod
import json
import re
import random
from urllib.parse import urljoin, urlparse

import feedparser
from lxml import html as lxml_html
import requests as _requests
import trafilatura

MAX_ARTICLE_CHARS = 2000


# ── Limpeza de texto RSS ───────────────────────────────────────────────────────

_HTML_TAG_RE         = re.compile(r'<[^>]+>')
_AUTHOR_LINE_RE      = re.compile(r'^Por\s+\w.{0,100}[\|•]', re.IGNORECASE)
_CAPTION_LINE_RE     = re.compile(r'^(—\s*)?(Foto|Imagem|Crédito|Legenda|Reprodução)\s*[:/]', re.IGNORECASE)
_TRAILING_CAPTION_RE = re.compile(r'\s+[—–]\s*(Foto|Imagem|Crédito|Legenda|Reprodução)\s*[:/].{0,120}$', re.IGNORECASE)
_PROMO_EMOJI_RE      = re.compile(
    r'^[\U0001F300-\U0001FFFF☀-➿✂-➰➡👉🔗✅⚡🎯]\s*'
    r'(Compre|Garanta|Acesse|Clique|Veja|Baixe|Aproveite|Confira agora)',
    re.IGNORECASE,
)
_RSS_SECTION_RE = re.compile(
    r'^(LEIA TAMB[EÉ]M|ASSISTA (AOS )?V[ÍI]DEOS|NOSSOS V[ÍI]DEOS|V[ÍI]DEOS (EM DESTAQUE|RELACIONADOS)|'
    r'VEJA TAMB[EÉ]M|MAIS NOT[ÍI]CIAS|OUTROS DESTAQUES|CONTINUE LENDO|'
    r'YOU MAY ALSO LIKE|RELATED ARTICLES|VOC[ÊE] TAMB[ÉE]M PODE|CONFIRA TAMB[EÉ]M)\b',
    re.IGNORECASE,
)


def _clean_rss_text(title: str, text: str) -> str:
    if not text:
        return ''
    # Decodifica entidades HTML e remove tags residuais (fallback do Google News)
    text = _html_mod.unescape(text)
    text = _HTML_TAG_RE.sub(' ', text)
    # Normaliza espaços horizontais por linha, preservando quebras de linha
    # \xa0 = non-breaking space gerado por &nbsp;
    lines_raw = text.splitlines()
    lines = [re.sub(r'[ \t\xa0]+', ' ', ln).strip() for ln in lines_raw]

    out = []
    skip_section = False
    for line in lines:
        s = line.strip()
        if _RSS_SECTION_RE.match(s):
            skip_section = True
            continue
        if skip_section:
            if not s:
                skip_section = False
            continue
        # Remove linha se for idêntica ao título (duplicação comum do trafilatura)
        if title and s == title.strip():
            continue
        if _AUTHOR_LINE_RE.match(s):
            continue
        if _CAPTION_LINE_RE.match(s):
            continue
        if _PROMO_EMOJI_RE.match(s):
            continue
        # Remove legenda de foto no final de uma linha com conteúdo real
        s = _TRAILING_CAPTION_RE.sub('', s).strip()
        if s:
            out.append(s)

    # Colapsa linhas em branco consecutivas
    result = []
    prev_blank = False
    for line in out:
        blank = not line
        if blank and prev_blank:
            continue
        result.append(line)
        prev_blank = blank

    cleaned = '\n'.join(result).strip()
    return cleaned if len(cleaned) >= 20 else ''
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


def _sanitize_date(dt: datetime | None) -> datetime | None:
    """Retorna None para datas claramente erradas (bug de migração de CMS: ano < 2020)."""
    if dt is not None and dt.year < 2020:
        return None
    return dt


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
            published = _sanitize_date(_parse_date(entry))
            if published and published < cutoff:
                continue
            url = entry.get('link', '')
            title = entry.get('title', '').strip()
            if not url or not title:
                continue
            summary = entry.get('summary', '')
            raw = _extract_text(url) or summary[:MAX_ARTICLE_CHARS]
            text = _clean_rss_text(title, raw)
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
    days_lookback = settings.get('days_lookback', 1)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)

    shuffled = random.sample(feeds, len(feeds))
    scrape_feeds = [f for f in shuffled if f.get('scrape')]
    rss_feeds = [f for f in shuffled if not f.get('scrape')]

    all_items: list[dict] = []

    # fontes scrape rodam em paralelo (IO-bound)
    # Consulta todos os feeds sem parar cedo: o caller filtra seen_ids e aplica max_total
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

    # fontes RSS nativas rodam sequencialmente
    # Sem early-stop por max_total: feeds posteriores podem ter conteúdo novo
    # após o filtro de histórico aplicado pelo caller
    for feed_config in rss_feeds:
        feed_name = feed_config.get('name', '')
        feed_url  = feed_config['url']
        # user_agent por feed: alguns sites bloqueiam o UA padrão do feedparser/Chrome
        custom_ua = feed_config.get('user_agent')
        if custom_ua:
            try:
                r = _requests.get(feed_url, timeout=_HTTP_TIMEOUT,
                                   headers={**_HTTP_HEADERS, 'User-Agent': custom_ua})
                feed = feedparser.parse(r.content)
            except Exception:
                feed = feedparser.parse(feed_url)
        else:
            feed = feedparser.parse(feed_url)
        if not feed_name:
            feed_name = feed.feed.get('title', 'Feed')
        count = 0

        for entry in feed.entries:
            if count >= max_per_feed:
                break
            published = _parse_date(entry)
            if published and published < cutoff:
                continue
            url = entry.get('link', '')
            title = entry.get('title', '').strip()
            if not url or not title:
                continue
            summary = entry.get('summary', '')
            raw = _extract_text(url) or summary[:MAX_ARTICLE_CHARS]
            text = _clean_rss_text(title, raw)
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
