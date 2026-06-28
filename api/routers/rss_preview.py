import html as _html
import re
from datetime import datetime, timezone

import feedparser
from fastapi import APIRouter, HTTPException, Query

from api.services.config_service import get_sources

router = APIRouter(tags=["rss-preview"])

_HTML_TAG_RE = re.compile(r"<[^>]+>")


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
            "feeds": [{"name": f.get("name", ""), "url": f["url"]} for f in feeds],
        })
    return result


@router.get("/rss/preview")
def preview_feed(url: str = Query(...)):
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
        title = entry.get("title", "").strip()
        url_item = entry.get("link", "")
        summary = _clean_summary(
            entry.get("summary", "") or entry.get("description", "")
        )
        items.append({
            "title": title,
            "url": url_item,
            "published_at": _parse_date(entry),
            "summary": summary,
        })

    return {
        "feed_title": feed_meta.get("title", ""),
        "feed_description": feed_meta.get("description", "") or feed_meta.get("subtitle", ""),
        "feed_link": feed_meta.get("link", ""),
        "total": len(items),
        "items": items,
    }
