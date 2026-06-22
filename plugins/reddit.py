import html
import random
import re
from datetime import datetime, timezone, timedelta

import feedparser

REDDIT_RSS = 'https://www.reddit.com/r/{subreddit}/top/.rss?t={timeframe}'


def _clean_summary(summary: str) -> str:
    text = html.unescape(summary)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'submitted by.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[link\]|\[comments\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:600]


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings    = source_config.get('settings', {})
    subreddits  = list(source_config.get('subreddits', ['brasil']))
    max_per_sub = settings.get('max_per_subreddit', 3)
    max_total   = settings.get('max_total', 10)
    timeframe   = settings.get('timeframe', 'day')

    random.shuffle(subreddits)
    all_items = []

    for subreddit in subreddits:
        if len(all_items) >= max_total:
            break

        url  = REDDIT_RSS.format(subreddit=subreddit, timeframe=timeframe)
        feed = feedparser.parse(url)

        if not feed.entries:
            print(f"  [reddit/r/{subreddit}] sem entradas")
            continue

        count = 0
        for entry in feed.entries:
            if count >= max_per_sub or len(all_items) >= max_total:
                break

            title = entry.get('title', '').strip()
            link  = entry.get('link', '')
            if not title or not link:
                continue

            summary = _clean_summary(entry.get('summary', ''))

            published = None
            if entry.get('published_parsed'):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            pub_iso = (published or datetime.now(timezone.utc)).isoformat()

            all_items.append({
                'id':           f"reddit-{subreddit}-{abs(hash(link))}",
                'title':        title,
                'url':          link,
                'text':         summary,
                'source_name':  f"r/{subreddit}",
                'source_type':  'reddit',
                'published_at': pub_iso,
                'views':        0,
                'num_comments': 0,
                'comments':     [],
                'channel':      f"r/{subreddit}",
            })
            count += 1
            print(f"  [r/{subreddit}] {title[:65]}")

    return all_items[:max_total]
