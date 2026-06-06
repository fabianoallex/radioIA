import html
import random
import requests
from datetime import date

OPENTDB_API = 'https://opentdb.com/api.php'

DIFFICULTY_PT = {'easy': 'fácil', 'medium': 'médio', 'hard': 'difícil'}


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings   = source_config.get('settings', {})
    amount     = settings.get('amount', 5)
    category   = settings.get('category')
    difficulty = settings.get('difficulty')
    today      = date.today().strftime('%Y%m%d')

    params: dict = {'amount': amount, 'type': 'multiple'}
    if category:
        params['category'] = category
    if difficulty:
        params['difficulty'] = difficulty

    try:
        resp = requests.get(OPENTDB_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('response_code') != 0:
            print(f"  [trivia] API retornou code {data.get('response_code')}")
            return []
    except Exception as e:
        print(f"  [trivia] Erro: {e}")
        return []

    items = []
    for q in data.get('results', []):
        question      = html.unescape(q['question'])
        correct       = html.unescape(q['correct_answer'])
        incorrect     = [html.unescape(a) for a in q['incorrect_answers']]
        category_name = html.unescape(q['category'])
        difficulty_pt = DIFFICULTY_PT.get(q['difficulty'], q['difficulty'])

        options = incorrect + [correct]
        random.shuffle(options)
        options_text = ' | '.join(f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options))

        items.append({
            'id':           f"trivia-{today}-{abs(hash(question))}",
            'title':        question,
            'url':          '',
            'text':         f"Opcoes: {options_text}\nResposta correta: {correct}\nCategoria: {category_name}\nDificuldade: {difficulty_pt}",
            'source_name':  category_name,
            'source_type':  'trivia',
            'published_at': date.today().isoformat(),
            'views':        0,
            'comments':     [],
            'channel':      category_name,
        })
        print(f"  [{difficulty_pt}] {question[:70]}")

    return items
