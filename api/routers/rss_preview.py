import html as _html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import feedparser
from fastapi import APIRouter, HTTPException, Query

from api.services.config_service import get_sources
from src.sources.rss import (
    _clean_rss_text,
    _extract_article,
    _fetch_html,
    _find_rss_in_html,
    _scrape_page_links,
)

router = APIRouter(tags=["rss-preview"])

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MAX_PREVIEW_SCRAPE = 8


def _parse_date(entry) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return None


def _clean_summary(text: str) -> str:
    if not text:
        return ""
    text = _html.unescape(text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


@router.get("/rss/feeds")
def list_rss_feeds():
    result = []
    for src in get_sources():
        if src.get("type") != "rss":
            continue
        feeds = src.get("feeds") or src.get("settings", {}).get("feeds") or []
        if not feeds:
            continue
        result.append({
            "source_id": src["id"],
            "source_name": src.get("name", src["id"]),
            "enabled": src.get("enabled", True),
            "feeds": [
                {
                    "name": f.get("name", ""),
                    "url": f["url"],
                    "scrape": bool(f.get("scrape", False)),
                }
                for f in feeds
            ],
        })
    return result


@router.get("/rss/preview")
def preview_feed(url: str = Query(...), scrape: bool = Query(False)):
    if scrape:
        return _scrape_preview(url)
    return _rss_preview(url)


# ── Modo RSS normal ────────────────────────────────────────────────────────────

def _rss_preview(url: str) -> dict:
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if feed.bozo and not feed.entries:
        detail = str(feed.bozo_exception) if feed.bozo_exception else "Feed inválido ou inacessível"
        raise HTTPException(status_code=400, detail=detail)

    feed_meta = feed.feed
    items = []
    for entry in feed.entries[:25]:
        items.append({
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "published_at": _parse_date(entry),
            "summary": _clean_summary(
                entry.get("summary", "") or entry.get("description", "")
            ),
        })

    return {
        "feed_title": feed_meta.get("title", ""),
        "feed_description": feed_meta.get("description", "") or feed_meta.get("subtitle", ""),
        "feed_link": feed_meta.get("link", ""),
        "via_rss": None,
        "total": len(items),
        "items": items,
    }


# ── Modo scrape ────────────────────────────────────────────────────────────────

def _scrape_preview(page_url: str) -> dict:
    html = _fetch_html(page_url)
    if not html:
        raise HTTPException(status_code=400, detail="Página inacessível")

    # 1. Auto-descoberta de RSS no <head>
    rss_url = _find_rss_in_html(html, page_url)
    if rss_url:
        try:
            feed = feedparser.parse(rss_url)
            if feed.entries:
                items = []
                for entry in feed.entries[:_MAX_PREVIEW_SCRAPE]:
                    items.append({
                        "title": entry.get("title", "").strip(),
                        "url": entry.get("link", ""),
                        "published_at": _parse_date(entry),
                        "summary": _clean_summary(
                            entry.get("summary", "") or entry.get("description", "")
                        ),
                    })
                feed_meta = feed.feed
                return {
                    "feed_title": feed_meta.get("title", ""),
                    "feed_description": feed_meta.get("description", "") or feed_meta.get("subtitle", ""),
                    "feed_link": feed_meta.get("link", ""),
                    "via_rss": rss_url,
                    "total": len(items),
                    "items": items,
                }
        except Exception:
            pass

    # 2. Fallback: scraping de links + extração por trafilatura (paralelo)
    candidates = _scrape_page_links(page_url)[:_MAX_PREVIEW_SCRAPE * 2]

    results: dict[str, tuple[str, str, datetime | None]] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {
            executor.submit(_extract_article, link): link for link in candidates
        }
        for future in as_completed(future_to_url):
            link = future_to_url[future]
            try:
                results[link] = future.result()
            except Exception:
                results[link] = ("", "", None)

    items = []
    for link in candidates:
        if len(items) >= _MAX_PREVIEW_SCRAPE:
            break
        title, text, published = results.get(link, ("", "", None))
        if not title or not text:
            continue
        cleaned = _clean_rss_text(title, text)
        items.append({
            "title": title,
            "url": link,
            "published_at": published.isoformat() if published else None,
            "summary": cleaned[:600],
        })

    return {
        "feed_title": "",
        "feed_description": "",
        "feed_link": page_url,
        "via_rss": None,
        "total": len(items),
        "items": items,
    }
