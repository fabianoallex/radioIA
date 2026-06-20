"""
GitHub Trending plugin para RadioIA

Busca os repositórios em alta no GitHub e gera um episódio com os destaques
da programação open source do período.

Para usar, adicione ao config.yaml:
  - id: github-trending
    type: github_trending
    name: "GitHub em Alta"
    enabled: true
    settings:
      since: daily        # daily | weekly | monthly
      language: ""        # ex: python, javascript (vazio = todas)
      max_items: 5
"""

import re
import requests
from datetime import date, datetime, timezone
from bs4 import BeautifulSoup

TRENDING_URL = 'https://github.com/trending'

PERIOD_PT = {
    'daily':   'hoje',
    'weekly':  'esta semana',
    'monthly': 'este mês',
}

METADATA = {
    'name':        'GitHub Trending',
    'description': 'Repositórios em alta no GitHub (diário, semanal ou mensal)',
    'icon':        'github',
    'credentials': [],
    'config_schema': [
        {
            'key': 'since', 'label': 'Período', 'type': 'select',
            'options': ['daily', 'weekly', 'monthly'], 'default': 'daily',
        },
        {'key': 'language',  'label': 'Linguagem (opcional)', 'type': 'text',   'default': ''},
        {'key': 'max_items', 'label': 'Máx. repositórios',   'type': 'number', 'default': 5},
    ],
}


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _parse_stars(text: str) -> int:
    m = re.search(r'\d+', text.replace(',', '').replace('.', ''))
    return int(m.group()) if m else 0


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings  = source_config.get('settings') or {}
    since     = settings.get('since', 'daily')
    language  = settings.get('language', '') or ''
    max_items = int(settings.get('max_items', 5))
    today     = date.today().isoformat()
    period_pt = PERIOD_PT.get(since, since)

    params = {'since': since}
    if language:
        params['l'] = language

    try:
        resp = requests.get(
            TRENDING_URL,
            params=params,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadioIA/1.0)'},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f'  [github_trending] Erro ao buscar trending: {e}')
        return []

    soup     = BeautifulSoup(resp.text, 'html.parser')
    articles = soup.select('article.Box-row')

    if not articles:
        print('  [github_trending] Nenhum repositório encontrado — HTML pode ter mudado')
        return []

    items = []
    for article in articles[:max_items]:
        h2 = article.select_one('h2 a')
        if not h2:
            continue

        # "pallets / flask" -> owner="pallets", repo="flask"
        parts = [p.strip() for p in _clean(h2.get_text()).split('/')]
        if len(parts) != 2 or not all(parts):
            continue
        owner, repo = parts
        full_name   = f'{owner}/{repo}'

        desc_el     = article.select_one('p')
        description = _clean(desc_el.get_text()) if desc_el else ''

        lang_el       = article.select_one('[itemprop="programmingLanguage"]')
        language_name = _clean(lang_el.get_text()) if lang_el else ''

        star_link  = article.select_one('a[href$="/stargazers"]')
        total_stars = _parse_stars(star_link.get_text()) if star_link else 0

        period_el   = article.select_one('.float-sm-right')
        stars_period = _parse_stars(period_el.get_text()) if period_el else 0

        url = f'https://github.com/{full_name}'

        lang_line = f'Linguagem: {language_name}\n' if language_name else ''
        text = (
            f'Repositório: {full_name}\n'
            f'Autor: {owner}\n'
            f'{lang_line}'
            f'Descrição: {description or "sem descrição"}\n'
            f'Estrelas totais: {total_stars:,}\n'
            f'Estrelas ganhas {period_pt}: {stars_period}'
        )

        items.append({
            'id':           f'github-trending-{owner}-{repo}-{today}',
            'title':        full_name,
            'url':          url,
            'text':         text,
            'source_name':  source_config.get('name', 'GitHub Trending'),
            'source_type':  source_config.get('type', 'github_trending'),
            'published_at': datetime.now(timezone.utc).isoformat(),
            'views':        total_stars,
            'comments':     [],
            'channel':      language_name or 'GitHub',
        })
        print(f'  [{language_name or "?"}] {full_name} — {stars_period} stars {period_pt}')

    return items
