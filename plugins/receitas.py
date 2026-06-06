import random
import requests
import feedparser
import trafilatura
from datetime import date

MEALDB_RANDOM = 'https://www.themealdb.com/api/json/v1/1/random.php'
MEALDB_FILTER = 'https://www.themealdb.com/api/json/v1/1/filter.php'
MEALDB_LOOKUP = 'https://www.themealdb.com/api/json/v1/1/lookup.php'

MAX_RECIPE_CHARS = 3000
MAX_RSS_CANDIDATES = 15   # entradas do feed consideradas por execução
MAX_RSS_FETCH_TRIES = 5   # quantas URLs tentamos buscar antes de desistir

AREA_PT = {
    'Italian':    'Italiana',   'Mexican':    'Mexicana',
    'American':   'Americana',  'French':     'Francesa',
    'Spanish':    'Espanhola',  'Japanese':   'Japonesa',
    'Indian':     'Indiana',    'Moroccan':   'Marroquina',
    'Portuguese': 'Portuguesa', 'Greek':      'Grega',
    'Turkish':    'Turca',      'Thai':       'Tailandesa',
    'Chinese':    'Chinesa',    'Malaysian':  'Malaio',
    'British':    'Britânica',  'Argentine':  'Argentina',
    'Peruvian':   'Peruana',    'Egyptian':   'Egípcia',
    'Unknown':    '',
}

CATEGORY_PT = {
    'Beef': 'Carne bovina', 'Chicken': 'Frango', 'Pork': 'Porco',
    'Lamb': 'Cordeiro', 'Seafood': 'Frutos do mar', 'Pasta': 'Massa',
    'Dessert': 'Sobremesa', 'Vegetarian': 'Vegetariana', 'Vegan': 'Vegana',
    'Breakfast': 'Café da manhã', 'Starter': 'Entrada', 'Side': 'Acompanhamento',
    'Miscellaneous': 'Variada',
}


# ── RSS (sites brasileiros) ────────────────────────────────────────────────────

def _fetch_from_rss(feeds: list[dict]) -> dict | None:
    candidates = []
    for feed_config in random.sample(feeds, len(feeds)):
        try:
            feed = feedparser.parse(feed_config['url'])
            feed_name = feed_config.get('name') or feed.feed.get('title', 'Receitas')
            for entry in feed.entries[:MAX_RSS_CANDIDATES]:
                url  = entry.get('link', '').strip()
                title = entry.get('title', '').strip()
                if url and title:
                    candidates.append({'url': url, 'title': title, 'feed_name': feed_name})
        except Exception as e:
            print(f"  [receitas/rss/{feed_config.get('name')}] {e}")

    if not candidates:
        return None

    random.shuffle(candidates)
    for candidate in candidates[:MAX_RSS_FETCH_TRIES]:
        try:
            downloaded = trafilatura.fetch_url(candidate['url'])
            if not downloaded:
                continue
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            ) or ''
            if len(text) < 200:
                continue
            print(f"  Receita: {candidate['title']} ({candidate['feed_name']})")
            return {**candidate, 'text': text[:MAX_RECIPE_CHARS]}
        except Exception as e:
            print(f"  [receitas/rss] {e}")

    return None


# ── TheMealDB ─────────────────────────────────────────────────────────────────

def _ingredients(meal: dict) -> list[str]:
    result = []
    for i in range(1, 21):
        ing = (meal.get(f'strIngredient{i}') or '').strip()
        msr = (meal.get(f'strMeasure{i}') or '').strip()
        if ing:
            result.append(f"{msr} de {ing}" if msr else ing)
    return result


def _fetch_by_area(area: str) -> dict | None:
    try:
        r = requests.get(MEALDB_FILTER, params={'a': area}, timeout=10)
        r.raise_for_status()
        meals = r.json().get('meals') or []
        if not meals:
            return None
        meal_id = random.choice(meals)['idMeal']
        r2 = requests.get(MEALDB_LOOKUP, params={'i': meal_id}, timeout=10)
        r2.raise_for_status()
        return r2.json()['meals'][0]
    except Exception as e:
        print(f"  [receitas/{area}] {e}")
        return None


def _fetch_random() -> dict | None:
    try:
        r = requests.get(MEALDB_RANDOM, timeout=10)
        r.raise_for_status()
        return r.json()['meals'][0]
    except Exception as e:
        print(f"  [receitas/random] {e}")
        return None


# ── entry point ───────────────────────────────────────────────────────────────

def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings  = source_config.get('settings') or {}
    feeds     = settings.get('feeds', [])
    areas     = settings.get('areas', [])
    today     = date.today().isoformat()

    # ── RSS: sites brasileiros ────────────────────────────────────────────────
    if feeds:
        data = _fetch_from_rss(feeds)
        if data:
            return [{
                'id':           f"receita-{abs(hash(data['url'])) % 10**8}-{today}",
                'title':        data['title'],
                'url':          data['url'],
                'text':         data['text'],
                'source_name':  data['feed_name'],
                'source_type':  'receitas',
                'published_at': today,
                'views':        0,
                'comments':     [],
                'channel':      data['feed_name'],
            }]
        print("  [receitas] RSS sem resultado — tentando TheMealDB...")

    # ── TheMealDB: fallback (ou modo principal sem feeds) ────────────────────
    meal = None
    if areas:
        for area in random.sample(areas, len(areas)):
            meal = _fetch_by_area(area)
            if meal:
                break
    if not meal:
        meal = _fetch_random()

    if not meal:
        return []

    name         = meal.get('strMeal', '')
    area_en      = meal.get('strArea', '')
    category_en  = meal.get('strCategory', '')
    instructions = (meal.get('strInstructions') or '').strip()
    source_url   = meal.get('strSource', '')
    area_pt      = AREA_PT.get(area_en, area_en)
    category_pt  = CATEGORY_PT.get(category_en, category_en)
    ingredients  = _ingredients(meal)

    ing_text = '\n'.join(f"- {i}" for i in ingredients)
    text = (
        f"Culinária: {area_pt or area_en}\n"
        f"Categoria: {category_pt or category_en}\n\n"
        f"Ingredientes:\n{ing_text}\n\n"
        f"Modo de preparo:\n{instructions[:2000]}"
    )

    print(f"  Receita: {name} ({area_pt or area_en})")

    return [{
        'id':           f"receita-{meal.get('idMeal','')}-{today}",
        'title':        name,
        'url':          source_url,
        'text':         text,
        'source_name':  f"Culinária {area_pt}" if area_pt else 'Receita do Dia',
        'source_type':  'receitas',
        'published_at': today,
        'views':        0,
        'comments':     [],
        'channel':      area_pt or category_pt,
    }]
