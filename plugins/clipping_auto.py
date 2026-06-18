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
      max_topics: 3           # quantos tópicos pedir ao LLM (usa o 1º não-recente)
      max_sources: 5          # veículos por tópico
      days_lookback: 1
      fetch_content: true
      max_content_chars: 2000
      llm_model: claude-haiku-4-5-20251001
      topic_history_days: 7   # evita repetir assunto coberto nos últimos N dias
      agregadores:
        - google_news
        - bing_news
      trending_feeds:         # RSS dos portais para descoberta de manchetes
        - https://g1.globo.com/rss/g1/
        - https://feeds.folha.uol.com.br/emcimadahora/rss091.xml
        - https://feeds.bbci.co.uk/portuguese/rss.xml
        - https://rss.uol.com.br/feed/noticias.xml
"""

import json
import os
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

DEFAULT_LLM_MODEL    = 'claude-haiku-4-5-20251001'
MAX_HEADLINES_PER_FEED = 40
HISTORY_PATH         = os.path.join('output', '_clipping_auto_history.json')
HISTORY_KEEP_DAYS    = 90   # mantém histórico por 90 dias, independente do filtro

_STOPWORDS = {'de', 'da', 'do', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
              'e', 'o', 'a', 'os', 'as', 'um', 'uma', 'por', 'para', 'com',
              'que', 'se', 'ao', 'aos', 'às', 'sobre', 'entre', 'após'}


# ── Histórico de tópicos ──────────────────────────────────────────────────────

def _load_recent_topics(history_days: int) -> list[str]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            history = json.load(f)
        cutoff = (date.today() - timedelta(days=history_days)).isoformat()
        return [e['topic'] for e in history if e.get('date', '') >= cutoff]
    except Exception:
        return []


def _save_topic(topic: str) -> None:
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append({'topic': topic, 'date': date.today().isoformat()})
    cutoff = (date.today() - timedelta(days=HISTORY_KEEP_DAYS)).isoformat()
    history = [e for e in history if e.get('date', '') >= cutoff]
    os.makedirs('output', exist_ok=True)
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _is_similar(topic: str, recent: list[str], threshold: float = 0.4) -> bool:
    """True se o tópico compartilha palavras-chave com algum tópico recente."""
    words = set(topic.lower().split()) - _STOPWORDS
    for r in recent:
        r_words = set(r.lower().split()) - _STOPWORDS
        if not words or not r_words:
            continue
        overlap = len(words & r_words) / len(words | r_words)
        if overlap >= threshold:
            return True
    return False


# ── Coleta de manchetes ───────────────────────────────────────────────────────

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


# ── Descoberta de tópicos via LLM ─────────────────────────────────────────────

def _discover_topics(headlines: list[str], max_topics: int,
                     recent_topics: list[str],
                     model: str, api_base: str | None) -> list[str]:
    if not headlines:
        return []
    headlines_text = '\n'.join(f'- {h}' for h in headlines)

    avoid_block = ''
    if recent_topics:
        avoid_list = '\n'.join(f'- {t}' for t in recent_topics)
        avoid_block = (
            f'\nAssuntos ja cobertos recentemente (EVITE repetir ou escolha angulo '
            f'completamente diferente):\n{avoid_list}\n'
        )

    prompt = (
        f'Abaixo estao manchetes recentes de portais de noticias brasileiros.\n'
        f'Identifique os {max_topics} assunto(s) mais relevantes do dia '
        f'(mais recorrentes e de maior impacto jornalistico).\n'
        f'{avoid_block}'
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


# ── Entry point ───────────────────────────────────────────────────────────────

def fetch(source_config: dict, credentials=None) -> list[dict]:
    from plugins import clipping as clipping_plugin

    settings          = source_config.get('settings') or {}
    max_topics        = int(settings.get('max_topics', 3))
    model             = settings.get('llm_model', DEFAULT_LLM_MODEL)
    feeds             = settings.get('trending_feeds', DEFAULT_TRENDING_FEEDS)
    days_lookback     = int(settings.get('days_lookback', 1))
    history_days      = int(settings.get('topic_history_days', 7))

    api_base = None
    try:
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        api_base = (cfg.get('llm') or cfg.get('claude') or {}).get('api_base')
    except Exception:
        pass

    since          = date.today() - timedelta(days=days_lookback)
    recent_topics  = _load_recent_topics(history_days)
    if recent_topics:
        print(f'  [clipping-auto] {len(recent_topics)} topico(s) recente(s) a evitar.')

    print(f'  [clipping-auto] coletando manchetes de {len(feeds)} feed(s)...')
    headlines = _collect_headlines(feeds, since)
    print(f'  [clipping-auto] {len(headlines)} manchete(s) coletada(s).')
    if not headlines:
        print('  [clipping-auto] nenhuma manchete disponivel — abortando.')
        return []

    # Pede mais tópicos do que o necessário para ter alternativas caso os primeiros sejam recentes
    ask_for = max(max_topics, len(recent_topics) + 3)
    print(f'  [clipping-auto] identificando topico(s) via LLM ({model})...')
    topics = _discover_topics(headlines, ask_for, recent_topics, model, api_base)
    if not topics:
        print('  [clipping-auto] LLM nao retornou topicos — abortando.')
        return []

    # Seleciona o primeiro tópico que não seja similar a um recente
    topic = None
    for candidate in topics:
        if not _is_similar(candidate, recent_topics):
            topic = candidate
            break

    if topic is None:
        # Todos são similares a recentes — usa o primeiro mesmo assim
        topic = topics[0]
        print(f'  [clipping-auto] todos os topicos sao recentes; usando o mais relevante.')

    print(f'  [clipping-auto] topico selecionado: "{topic}"')
    _save_topic(topic)

    source_config['name'] = f'Clipping — {topic[:60]}'

    clipping_config = {
        **source_config,
        'type': 'clipping',
        'settings': {**settings, 'topic': topic},
    }
    return clipping_plugin.fetch(clipping_config, credentials)
