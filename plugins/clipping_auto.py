"""
Plugin RadioIA — Clipping Automático

Descobre o assunto mais discutido do dia consultando RSS de grandes portais
brasileiros e usando o LLM para identificar o tópico principal. A seguir,
busca cobertura usando o fluxo normal de clipping.

Uso (via CLI, com o id configurado no config.yaml):
  python main.py clipping-auto

Ou como fonte agendada:
  - id: clipping-auto
    type: clipping_auto
    name: "Clipping do Dia"
    enabled: false      # acionar manualmente ou agendar na grade
    settings:
      max_topics: 1           # quantos tópicos pedir ao LLM (usa o 1º)
      max_sources: 5          # veículos por tópico
      days_lookback: 1
      fetch_content: true
      max_content_chars: 2000
      llm_model: claude-haiku-4-5-20251001
      agregadores:
        - google_news
        - bing_news
      trending_feeds:         # RSS dos portais para descoberta de manchetes
        - https://g1.globo.com/rss/g1/
        - https://feeds.folha.uol.com.br/emcimadahora/rss091.xml
        - https://feeds.bbci.co.uk/portuguese/rss.xml
        - https://rss.uol.com.br/feed/noticias.xml
"""

import re
from datetime import date, timedelta

import feedparser
import litellm

litellm.suppress_debug_info = True

DEFAULT_TRENDING_FEEDS = [
    'https://g1.globo.com/rss/g1/',
    'https://feeds.folha.uol.com.br/emcimadahora/rss091.xml',
    'https://feeds.bbci.co.uk/portuguese/rss.xml',
    'https://rss.uol.com.br/feed/noticias.xml',
]

DEFAULT_LLM_MODEL = 'claude-haiku-4-5-20251001'
MAX_HEADLINES_PER_FEED = 40


def _collect_headlines(feeds: list[str], since: date) -> list[str]:
    headlines = []
    seen: set[str] = set()
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:MAX_HEADLINES_PER_FEED]:
                title = entry.get('title', '').strip()
                if not title or title in seen:
                    continue
                try:
                    import email.utils
                    pub = email.utils.parsedate_to_datetime(entry.get('published', '')).date()
                    if pub < since:
                        continue
                except Exception:
                    pass
                seen.add(title)
                headlines.append(title)
        except Exception as e:
            print(f'  [clipping-auto] erro ao ler feed {url}: {e}')
    return headlines


def _discover_topics(headlines: list[str], max_topics: int,
                     model: str, api_base: str | None) -> list[str]:
    if not headlines:
        return []
    headlines_text = '\n'.join(f'- {h}' for h in headlines)
    prompt = (
        f'Abaixo estao manchetes recentes de portais de noticias brasileiros.\n'
        f'Identifique os {max_topics} assunto(s) mais relevantes do dia '
        f'(mais recorrentes e de maior impacto jornalistico).\n'
        f'Responda APENAS com os topicos, um por linha, no formato exato:\n'
        f'TOPICO: frase curta de busca em portugues (maximo 6 palavras)\n\n'
        f'Manchetes:\n{headlines_text}'
    )
    kwargs = {'api_base': api_base} if api_base else {}
    try:
        response = litellm.completion(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=256,
            **kwargs,
        )
        text = response.choices[0].message.content or ''
        topics = re.findall(r'TOPICO:\s*(.+)', text)
        return [t.strip() for t in topics if t.strip()]
    except Exception as e:
        print(f'  [clipping-auto] erro ao consultar LLM: {e}')
        return []


def fetch(source_config: dict, credentials=None) -> list[dict]:
    from plugins import clipping as clipping_plugin

    settings      = source_config.get('settings') or {}
    max_topics    = int(settings.get('max_topics', 1))
    model         = settings.get('llm_model', DEFAULT_LLM_MODEL)
    feeds         = settings.get('trending_feeds', DEFAULT_TRENDING_FEEDS)
    days_lookback = int(settings.get('days_lookback', 1))

    api_base = None
    try:
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        api_base = (cfg.get('llm') or cfg.get('claude') or {}).get('api_base')
    except Exception:
        pass

    since = date.today() - timedelta(days=days_lookback)

    print(f'  [clipping-auto] coletando manchetes de {len(feeds)} feed(s)...')
    headlines = _collect_headlines(feeds, since)
    print(f'  [clipping-auto] {len(headlines)} manchete(s) coletada(s).')
    if not headlines:
        print('  [clipping-auto] nenhuma manchete disponivel — abortando.')
        return []

    print(f'  [clipping-auto] identificando topico(s) via LLM ({model})...')
    topics = _discover_topics(headlines, max_topics, model, api_base)
    if not topics:
        print('  [clipping-auto] LLM nao retornou topicos — abortando.')
        return []

    topic = topics[0]
    print(f'  [clipping-auto] topico selecionado: "{topic}"')

    # Atualiza o nome do episódio para refletir o tópico descoberto
    source_config['name'] = f'Clipping — {topic[:60]}'

    clipping_config = {
        **source_config,
        'type': 'clipping',
        'settings': {**settings, 'topic': topic},
    }
    return clipping_plugin.fetch(clipping_config, credentials)
