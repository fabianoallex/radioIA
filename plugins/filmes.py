import os
import random
import requests
from datetime import date

TMDB_BASE = 'https://api.themoviedb.org/3'

MODES = {
    'trending':    '/trending/movie/day',
    'now_playing': '/movie/now_playing',
    'upcoming':    '/movie/upcoming',
    'top_rated':   '/movie/top_rated',
}

MODE_LABEL = {
    'trending':    'Tendências',
    'now_playing': 'Em Cartaz',
    'upcoming':    'Em Breve',
    'top_rated':   'Mais Bem Avaliados',
}


def _get_genres(api_key: str, language: str) -> dict:
    try:
        r = requests.get(f'{TMDB_BASE}/genre/movie/list',
                         params={'api_key': api_key, 'language': language}, timeout=10)
        r.raise_for_status()
        return {g['id']: g['name'] for g in r.json().get('genres', [])}
    except Exception as e:
        print(f"  [filmes/generos] {e}")
        return {}


def _get_movies(api_key: str, mode: str, language: str, region: str, max_n: int) -> list[dict]:
    endpoint = MODES.get(mode, MODES['trending'])
    params   = {'api_key': api_key, 'language': language}
    if mode in ('now_playing', 'upcoming'):
        params['region'] = region
    try:
        r = requests.get(f'{TMDB_BASE}{endpoint}', params=params, timeout=10)
        r.raise_for_status()
        pool = r.json().get('results', [])
        # Embaralha para variedade a cada execução no mesmo dia
        random.shuffle(pool)
        return pool[:max_n]
    except Exception as e:
        print(f"  [filmes/{mode}] {e}")
        return []


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings   = source_config.get('settings') or {}
    api_key    = os.getenv(settings.get('api_key_env', 'TMDB_API_KEY'), '')
    mode       = settings.get('mode', 'trending')
    language   = settings.get('language', 'pt-BR')
    region     = settings.get('region', 'BR')
    max_movies = settings.get('max_movies', 5)
    today      = date.today().isoformat()

    if not api_key:
        print("  [filmes] TMDB_API_KEY não configurada — pulando.")
        return []

    genres = _get_genres(api_key, language)
    movies = _get_movies(api_key, mode, language, region, max_movies)

    if not movies:
        return []

    items = []
    for movie in movies:
        title       = movie.get('title', '')
        orig_title  = movie.get('original_title', '')
        overview    = (movie.get('overview') or '').strip()
        release     = (movie.get('release_date') or '')[:4]
        rating      = movie.get('vote_average', 0.0)
        votes       = movie.get('vote_count', 0)
        genre_names = ', '.join(
            genres[gid] for gid in movie.get('genre_ids', []) if gid in genres
        )

        title_str = f"{title}" if title == orig_title else f"{title} ({orig_title})"

        text = (
            f"Título original: {orig_title}\n"
            f"Ano: {release}\n"
            f"Gênero: {genre_names}\n"
            f"Nota: {rating:.1f}/10 ({votes:,} votos)\n"
            f"Sinopse: {overview[:600]}"
        )

        url = f"https://www.themoviedb.org/movie/{movie['id']}"
        print(f"  Filme: {title_str} ({release}) — {rating:.1f}/10")

        items.append({
            'id':           f"filme-{movie['id']}-{today}",
            'title':        title,
            'url':          url,
            'text':         text,
            'source_name':  source_config.get('name', 'Filmes'),
            'source_type':  'filmes',
            'published_at': today,
            'views':        int(movie.get('popularity', 0)),
            'comments':     [],
            'channel':      genre_names or 'Cinema',
        })

    return items
