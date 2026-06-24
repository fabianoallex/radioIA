"""
Plugin RadioIA — Web Radio (Relay de Rádio Externa)

Busca o MP3 atual de uma rádio web e inclui diretamente na programação da RadioIA,
sem geração de script ou TTS — o áudio externo é o conteúdo do episódio.

Duas estratégias de localização do MP3:

  1. page_url  — scraping da página: encontra a primeira tag <source src="...mp3">
                 ou <audio src="...mp3"> no HTML.

  2. direct_url — URL com tokens de data: constrói a URL diretamente sem scraping.

Tokens suportados em direct_url:
  {DDMMYYYY} → 24062026  |  {YYYYMMDD} → 20260624  |  {YYYY-MM-DD} → 2026-06-24
  {YYYY} → 2026  |  {MM} → 06  |  {DD} → 24  |  {HH} → 14  |  {MIN} → 30

Configuração em config.yaml:

  - id: radio-lar
    type: web_radio
    name: "Rádio LAR"
    enabled: true
    settings:
      # Estratégia 1: scraping
      page_url: "https://empresa.com/radio/"

      # Estratégia 2: URL direta com tokens de data (padrão LAR)
      direct_url: "https://empresa.com/wp-content/uploads/{YYYY}/{MM}/{DDMMYYYY}.mp3"

      user_agent: "Mozilla/5.0 ..."   # opcional, default: Chrome moderno
      timeout: 15                      # opcional, default: 15
"""

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests

BRT = timezone(timedelta(hours=-3))

_DEFAULT_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)

_TOKENS = {
    '{DDMMYYYY}':   lambda d: d.strftime('%d%m%Y'),
    '{YYYYMMDD}':   lambda d: d.strftime('%Y%m%d'),
    '{YYYY-MM-DD}': lambda d: d.strftime('%Y-%m-%d'),
    '{YYYY}':       lambda d: d.strftime('%Y'),
    '{MM}':         lambda d: d.strftime('%m'),
    '{DD}':         lambda d: d.strftime('%d'),
    '{HH}':         lambda d: d.strftime('%H'),
    '{MIN}':        lambda d: d.strftime('%M'),
}


def _expand(url: str, now: datetime) -> str:
    for token, fn in _TOKENS.items():
        url = url.replace(token, fn(now))
    return url


def _scrape_audio_url(page_url: str, user_agent: str, timeout: int) -> str | None:
    resp = requests.get(page_url, headers={'User-Agent': user_agent}, timeout=timeout)
    resp.raise_for_status()
    html = resp.text
    for pattern in [
        r'<source[^>]+src=["\']([^"\']+\.mp3[^"\']*)["\']',
        r'<audio[^>]+src=["\']([^"\']+\.mp3[^"\']*)["\']',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return urljoin(page_url, m.group(1))
    return None


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings   = source_config.get('settings') or {}
    page_url   = settings.get('page_url', '').strip()
    direct_url = settings.get('direct_url', '').strip()
    user_agent = settings.get('user_agent', _DEFAULT_UA)
    timeout    = int(settings.get('timeout', 15))

    now = datetime.now(BRT)

    if direct_url:
        audio_url = _expand(direct_url, now)
    elif page_url:
        try:
            audio_url = _scrape_audio_url(page_url, user_agent, timeout)
        except Exception as e:
            print(f'  [web-radio] Erro ao acessar página: {e}')
            return []
        if not audio_url:
            print(f'  [web-radio] Nenhum <audio> encontrado em {page_url}')
            return []
    else:
        print('  [web-radio] Configure page_url ou direct_url em settings')
        return []

    print(f'  [web-radio] MP3: {audio_url}')

    source_id  = source_config.get('id', 'web-radio')
    page_ref   = page_url or audio_url  # URL exibida no player/episode.json

    return [{
        'id':           f"{source_id}-{now.strftime('%Y-%m-%d')}",
        'title':        source_config.get('name', 'Rádio Externa'),
        'text':         '',
        'url':          page_ref,
        'audio_url':    audio_url,
        'source_name':  source_config.get('name', 'Rádio Externa'),
        'source_type':  source_config.get('type', 'web_radio'),
        'published_at': now.strftime('%Y-%m-%d'),
        'views':        0,
        'comments':     [],
        'channel':      source_config.get('name', 'Rádio Externa'),
    }]
