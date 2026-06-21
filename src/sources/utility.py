import json
import os
import shutil
from datetime import datetime, timedelta, timezone

import requests
from pydub import AudioSegment

LOTTERY_NAMES = {
    'megasena':   'Mega-Sena',
    'lotofacil':  'Lotofácil',
    'quina':      'Quina',
    'lotomania':  'Lotomania',
    'timemania':  'Timemania',
    'duplasena':  'Dupla Sena',
    'diadesorte': 'Dia de Sorte',
}

_MONTHS_PT = ['janeiro','fevereiro','março','abril','maio','junho',
              'julho','agosto','setembro','outubro','novembro','dezembro']

_WEEKDAYS_PT = ['segunda-feira','terça-feira','quarta-feira',
                'quinta-feira','sexta-feira','sábado','domingo']

_TEAM_PT = {
    'Brazil':'Brasil','Germany':'Alemanha','France':'França','Spain':'Espanha',
    'England':'Inglaterra','Italy':'Itália','Netherlands':'Holanda',
    'Portugal':'Portugal','Argentina':'Argentina','Uruguay':'Uruguai',
    'Mexico':'México','United States':'Estados Unidos','Japan':'Japão',
    'South Korea':'Coreia do Sul','Morocco':'Marrocos','Senegal':'Senegal',
    'Australia':'Austrália','Switzerland':'Suíça','Belgium':'Bélgica',
    'Croatia':'Croácia','Serbia':'Sérvia','Poland':'Polônia',
    'Denmark':'Dinamarca','Austria':'Áustria','Ecuador':'Equador',
    'Colombia':'Colômbia','Chile':'Chile','Peru':'Peru',
    'Venezuela':'Venezuela','Bolivia':'Bolívia','Paraguay':'Paraguai',
    'Canada':'Canadá','Saudi Arabia':'Arábia Saudita','Iran':'Irã',
    'Qatar':'Catar','Tunisia':'Tunísia','Cameroon':'Camarões',
    'Ghana':'Gana','Nigeria':'Nigéria',"Côte d'Ivoire":'Costa do Marfim',
    'Ivory Coast':'Costa do Marfim','Egypt':'Egito','Algeria':'Argélia',
    'Wales':'País de Gales','Scotland':'Escócia','Turkey':'Turquia',
    'Ukraine':'Ucrânia','Czech Republic':'República Tcheca',
    'Slovakia':'Eslováquia','Romania':'Romênia','Panama':'Panamá',
    'Costa Rica':'Costa Rica','Honduras':'Honduras','Jamaica':'Jamaica',
    'New Zealand':'Nova Zelândia','China':'China','Indonesia':'Indonésia',
}

BRT = timezone(timedelta(hours=-3))


def fetch(source_config: dict, credentials=None) -> list[dict]:
    data = _collect_data(source_config)
    text = _format_data_for_prompt(data)
    if not text:
        return []
    return [{
        'id':           f"utility-{source_config.get('id', 'utilidades')}-{datetime.now().strftime('%Y-%m-%d')}",
        'title':        source_config.get('name', 'Resumo do Dia'),
        'text':         text,
        'url':          '',
        'source_name':  source_config.get('name', 'Resumo do Dia'),
        'source_type':  'utility',
        'published_at': datetime.now().strftime('%Y-%m-%d'),
        'views':        0,
        'comments':     [],
        'channel':      source_config.get('name', 'Resumo do Dia'),
    }]


# ── Data fetchers ────────────────────────────────────────────────────────────

def _get_weather(city: str, api_key: str) -> dict | None:
    try:
        resp = requests.get(
            'https://api.openweathermap.org/data/2.5/weather',
            params={'q': city, 'appid': api_key, 'units': 'metric', 'lang': 'pt_br'},
            timeout=10
        )
        resp.raise_for_status()
        d = resp.json()
        return {
            'city':        d.get('name', city),
            'temp':        round(d['main']['temp']),
            'temp_min':    round(d['main']['temp_min']),
            'temp_max':    round(d['main']['temp_max']),
            'feels_like':  round(d['main']['feels_like']),
            'description': d['weather'][0]['description'],
            'humidity':    d['main']['humidity'],
        }
    except Exception as e:
        print(f"  [clima] {e}")
        return None


def _get_forecast(city: str, api_key: str, days: int) -> list[dict]:
    try:
        resp = requests.get(
            'https://api.openweathermap.org/data/2.5/forecast',
            params={'q': city, 'appid': api_key, 'units': 'metric', 'lang': 'pt_br', 'cnt': 40},
            timeout=10
        )
        resp.raise_for_status()
        data      = resp.json()
        city_name = data.get('city', {}).get('name', city)

        daily: dict[str, list] = {}
        for entry in data.get('list', []):
            daily.setdefault(entry['dt_txt'][:10], []).append(entry)

        today    = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        result   = []

        for date_str in sorted(daily.keys()):
            if date_str == today or len(result) >= days:
                continue
            entries   = daily[date_str]
            temp_min  = round(min(e['main']['temp_min'] for e in entries))
            temp_max  = round(max(e['main']['temp_max'] for e in entries))
            rain_prob = round(max(e.get('pop', 0) for e in entries) * 100)
            midday    = next((e for e in entries if '12:00:00' in e['dt_txt']), entries[len(entries) // 2])
            desc      = midday['weather'][0]['description']
            weekday   = _WEEKDAYS_PT[datetime.strptime(date_str, '%Y-%m-%d').weekday()]
            result.append({
                'city':      city_name,
                'label':     'amanhã' if date_str == tomorrow else weekday,
                'weekday':   weekday,
                'desc':      desc,
                'temp_min':  temp_min,
                'temp_max':  temp_max,
                'rain_prob': rain_prob,
            })

        return result
    except Exception as e:
        print(f"  [previsao/{city}] {e}")
        return []


def _get_finance(pairs: list[str]) -> list[dict]:
    try:
        resp = requests.get(
            f"https://economia.awesomeapi.com.br/json/last/{','.join(pairs)}",
            timeout=10
        )
        resp.raise_for_status()
        results = []
        for val in resp.json().values():
            results.append({
                'pair':       f"{val['code']}-{val['codein']}",
                'code':       val['code'],
                'bid':        float(val['bid']),
                'pct_change': float(val['pctChange']),
            })
        return results
    except Exception as e:
        print(f"  [financas] {e}")
        return []


# ── Ibovespa fetcher ─────────────────────────────────────────────────────────

BRAPI_LIST = 'https://brapi.dev/api/quote/list'


def _fmt_pontos(value: float) -> str:
    if value >= 1_000:
        k = value / 1_000
        return f"{k:.1f} mil pontos".replace('.', ' vírgula ')
    return f"{round(value)} pontos"


def _get_ibovespa(top_n: int = 3) -> dict:
    try:
        ibov_resp = requests.get(BRAPI_LIST, params={'search': 'ibovespa'}, timeout=10)
        ibov_resp.raise_for_status()
        ibov_stocks = ibov_resp.json().get('stocks', [])
        ibov = next((s for s in ibov_stocks if s['stock'] == 'IBOV11'), None)

        def _movers(order: str) -> list[dict]:
            r = requests.get(BRAPI_LIST, params={
                'sortBy': 'change', 'sortOrder': order,
                'limit': 40, 'type': 'stock',
            }, timeout=10)
            r.raise_for_status()
            stocks = r.json().get('stocks', [])
            filtered = [
                s for s in stocks
                if not s['stock'].endswith('F')
                and (s.get('volume') or 0) > 200_000
                and s.get('change') is not None
            ]
            return filtered[:top_n]

        altas  = _movers('desc')
        baixas = _movers('asc')

        result = {
            'pontos':  round(ibov['close']) if ibov else None,
            'change':  round(ibov['change'], 2) if ibov else None,
            'altas':   [{'ticker': s['stock'], 'change': round(s['change'], 2)} for s in altas],
            'baixas':  [{'ticker': s['stock'], 'change': round(s['change'], 2)} for s in baixas],
        }

        if result['pontos']:
            print(f"  Ibovespa: {result['pontos']:,} pts ({result['change']:+.2f}%)")
        for s in altas:
            print(f"  Alta  {s['ticker']:8} {s['change']:+.2f}%")
        for s in baixas:
            print(f"  Baixa {s['ticker']:8} {s['change']:+.2f}%")

        return result

    except Exception as e:
        print(f"  [ibovespa] {e}")
        return {}


# ── Lottery fetcher ──────────────────────────────────────────────────────────

def _fmt_date_pt(date_str: str) -> str:
    try:
        day, month, _ = date_str.split('/')
        return f"{int(day)} de {_MONTHS_PT[int(month) - 1]}"
    except Exception:
        return date_str


def _fmt_prize(value: float) -> str:
    if value >= 1_000_000:
        m = value / 1_000_000
        if m == round(m):
            return f"{round(m)} milhões de reais"
        return f"{m:.1f} milhões de reais".replace('.', ' vírgula ')
    if value >= 1_000:
        return f"{round(value / 1_000)} mil reais"
    return f"{round(value)} reais"


def _fmt_dezenas(dezenas: list[str]) -> str:
    return ', '.join(str(int(d)) for d in dezenas)


def _get_sun_times(lat: float, lng: float, tzid: str) -> dict | None:
    try:
        resp = requests.get(
            'https://api.sunrise-sunset.org/json',
            params={'lat': lat, 'lng': lng, 'tzid': tzid, 'formatted': 0},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'OK':
            return None
        r       = data['results']
        sunrise = datetime.fromisoformat(r['sunrise']).strftime('%H:%M')
        sunset  = datetime.fromisoformat(r['sunset']).strftime('%H:%M')
        secs    = int(r.get('day_length', 0))
        print(f"  Sol: nasce {sunrise} / se põe {sunset} ({secs // 3600}h{(secs % 3600) // 60:02d}min de luz)")
        return {
            'sunrise':      sunrise,
            'sunset':       sunset,
            'day_length_h': secs // 3600,
            'day_length_m': (secs % 3600) // 60,
        }
    except Exception as e:
        print(f"  [sol] {e}")
        return None


def _get_lottery(games: list[str]) -> list[dict]:
    results = []
    for game in games:
        try:
            resp = requests.get(
                f'https://servicebus2.caixa.gov.br/portaldeloterias/api/{game}',
                timeout=10,
                headers={'Accept': 'application/json'},
            )
            resp.raise_for_status()
            data = resp.json()
            top = data.get('listaRateioPremio', [{}])[0]
            entry = {
                'game':         game,
                'name':         LOTTERY_NAMES.get(game, game.title()),
                'numero':       data.get('numero', ''),
                'data':         _fmt_date_pt(data.get('dataApuracao', '')),
                'dezenas':      _fmt_dezenas(data.get('listaDezenas', [])),
                'acumulado':    data.get('acumulado', False),
                'ganhadores':   top.get('numeroDeGanhadores', 0),
                'valor_premio': top.get('valorPremio', 0.0),
                'proximo_valor': data.get('valorEstimadoProximoConcurso', 0.0),
                'proxima_data': _fmt_date_pt(data.get('dataProximoConcurso', '')),
            }
            results.append(entry)
            print(f"  {entry['name']}: concurso {entry['numero']}, {data.get('dataApuracao')}")
        except Exception as e:
            print(f'  [loteria/{game}] {e}')
    return results


# ── Football fetcher ─────────────────────────────────────────────────────────

def _team_pt(name: str) -> str:
    return _TEAM_PT.get(name, name)


def _get_football(competition: str, api_key: str) -> dict:
    now_brt       = datetime.now(BRT)
    today_brt     = now_brt.date()
    yesterday_brt = today_brt - timedelta(days=1)
    tomorrow_brt  = today_brt + timedelta(days=1)

    try:
        resp = requests.get(
            f'https://api.football-data.org/v4/competitions/{competition}/matches',
            params={'dateFrom': str(yesterday_brt), 'dateTo': str(tomorrow_brt)},
            headers={'X-Auth-Token': api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [futebol] {e}")
        return {}

    comp_name = data.get('competition', {}).get('name', 'Copa do Mundo')
    finished, today_games, live = [], [], []

    for m in data.get('matches', []):
        status = m.get('status', '')
        brt_dt = datetime.fromisoformat(
            m['utcDate'].replace('Z', '+00:00')
        ).astimezone(BRT)
        home = _team_pt(m['homeTeam'].get('name', ''))
        away = _team_pt(m['awayTeam'].get('name', ''))
        ft   = m.get('score', {}).get('fullTime', {})
        hs, as_ = ft.get('home'), ft.get('away')
        entry = {'home': home, 'away': away,
                 'home_score': hs, 'away_score': as_,
                 'time': brt_dt.strftime('%H:%M')}

        if status == 'FINISHED' and brt_dt.date() == yesterday_brt:
            finished.append(entry)
            print(f"  [futebol] {home} {hs}x{as_} {away}")
        elif status in ('SCHEDULED', 'TIMED') and brt_dt.date() == today_brt:
            today_games.append(entry)
            print(f"  [futebol] Hoje {brt_dt.strftime('%H:%M')}: {home} x {away}")
        elif status == 'IN_PLAY':
            live.append(entry)
            print(f"  [futebol] AO VIVO: {home} {hs}x{as_} {away}")

    return {'name': comp_name, 'finished': finished,
            'today': today_games, 'live': live}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pct(pct: float) -> str:
    if pct > 0.05:
        return f"em alta de {pct:.1f}%"
    if pct < -0.05:
        return f"em queda de {abs(pct):.1f}%"
    return "estável"


# ── Data collection + LLM prompt formatting ──────────────────────────────────

def _collect_data(source_config: dict) -> dict:
    settings = source_config.get('settings', {})
    data = {'clima': [], 'previsao': [], 'sol': None,
            'cambio': [], 'bolsa': {}, 'loterias': [], 'futebol': {}}

    wcfg = settings.get('weather', {})
    if wcfg.get('enabled', True):
        api_key       = os.getenv(wcfg.get('api_key_env', 'OPENWEATHER_API_KEY'), '')
        cities        = wcfg.get('cities') or ([wcfg['city']] if wcfg.get('city') else ['Sao Paulo'])
        forecast_days = wcfg.get('forecast_days', 0)
        if api_key:
            for city in cities:
                w = _get_weather(city, api_key)
                if w:
                    data['clima'].append(w)
                    print(f"  Clima {w['city']}: {w['description']}, {w['temp']}°C")
            if forecast_days > 0:
                for city in cities:
                    data['previsao'].extend(_get_forecast(city, api_key, forecast_days))
                    print(f"  Previsão {city}: {forecast_days} dia(s)")
        else:
            print("  [clima] OPENWEATHER_API_KEY não encontrada — pulando.")

    fcfg = settings.get('finance', {})
    if fcfg.get('enabled', True):
        pairs = fcfg.get('pairs', ['USD-BRL', 'EUR-BRL', 'BTC-BRL'])
        data['cambio'] = _get_finance(pairs)
        for item in data['cambio']:
            print(f"  {item['pair']}: R$ {item['bid']:.2f} ({_pct(item['pct_change'])})")

    lcfg = settings.get('lottery', {})
    if lcfg.get('enabled', False):
        games = lcfg.get('games', ['megasena', 'lotofacil'])
        data['loterias'] = _get_lottery(games)

    ftcfg = settings.get('football', {})
    if ftcfg.get('enabled', False):
        ft_key    = os.getenv(ftcfg.get('api_key_env', 'FOOTBALL_DATA_API_KEY'), '')
        comp_code = ftcfg.get('competition', 'WC')
        if ft_key:
            data['futebol'] = _get_football(comp_code, ft_key)
        else:
            print("  [futebol] FOOTBALL_DATA_API_KEY não encontrada — pulando.")

    icfg = settings.get('ibovespa', {})
    if icfg.get('enabled', False):
        top_n = icfg.get('top_movers', 3)
        data['bolsa'] = _get_ibovespa(top_n)

    scfg = settings.get('sun', {})
    if scfg.get('enabled', False):
        lat  = scfg.get('lat')
        lng  = scfg.get('lng')
        tzid = scfg.get('tzid', 'America/Sao_Paulo')
        if lat is not None and lng is not None:
            data['sol'] = _get_sun_times(lat, lng, tzid)
        else:
            print("  [sol] lat/lng não configurados — pulando.")

    return data


def _format_data_for_prompt(data: dict) -> str:
    parts = []

    if data.get('clima'):
        parts.append('[CLIMA]')
        for w in data['clima']:
            parts.append(
                f"{w['city']}: {w['description']}, {w['temp']}°C "
                f"(mín {w['temp_min']}° / máx {w['temp_max']}°), "
                f"sensação {w['feels_like']}°C, umidade {w['humidity']}%"
            )

    if data.get('previsao'):
        parts.append('[PREVISÃO]')
        for day in data['previsao']:
            rain = f", chance de chuva {day['rain_prob']}%" if day['rain_prob'] >= 30 else ''
            parts.append(
                f"{day['city']} — {day['label'].capitalize()}: "
                f"{day['desc']}, mín {day['temp_min']}° / máx {day['temp_max']}°{rain}"
            )

    if data.get('sol'):
        s = data['sol']
        parts.append('[SOL]')
        parts.append(
            f"Nascer: {s['sunrise']} | Pôr do sol: {s['sunset']} | "
            f"Dia: {s['day_length_h']}h{s['day_length_m']:02d}min de luz"
        )

    if data.get('cambio'):
        parts.append('[CÂMBIO]')
        for item in data['cambio']:
            parts.append(f"{item['pair']}: R$ {item['bid']:.2f} ({_pct(item['pct_change'])})")

    if data.get('bolsa') and data['bolsa'].get('pontos'):
        b = data['bolsa']
        parts.append('[BOLSA — Ibovespa]')
        parts.append(f"{b['pontos']:,} pontos | variação {b['change']:+.2f}%")
        if b.get('altas'):
            parts.append('Altas: ' + ', '.join(f"{s['ticker']} {s['change']:+.1f}%" for s in b['altas']))
        if b.get('baixas'):
            parts.append('Baixas: ' + ', '.join(f"{s['ticker']} {s['change']:+.1f}%" for s in b['baixas']))

    if data.get('loterias'):
        parts.append('[LOTERIAS]')
        for lot in data['loterias']:
            if lot['acumulado'] or lot['ganhadores'] == 0:
                status = f"Acumulou! Próximo: {_fmt_prize(lot['proximo_valor'])} em {lot['proxima_data']}"
            else:
                status = f"{lot['ganhadores']} ganhador(es) — {_fmt_prize(lot['valor_premio'])} cada"
            parts.append(
                f"{lot['name']} (concurso {lot['numero']}, {lot['data']}): "
                f"{lot['dezenas']} — {status}"
            )

    ft = data.get('futebol', {})
    if ft and (ft.get('finished') or ft.get('today') or ft.get('live')):
        parts.append(f"[FUTEBOL — {ft.get('name', 'Copa')}]")
        for m in ft.get('live', []):
            score = f"{m['home_score']}x{m['away_score']}" if m['home_score'] is not None else 'ao vivo'
            parts.append(f"AO VIVO: {m['home']} {score} {m['away']}")
        for m in ft.get('finished', []):
            parts.append(f"Ontem: {m['home']} {m['home_score']}x{m['away_score']} {m['away']}")
        for m in ft.get('today', []):
            parts.append(f"Hoje às {m['time']}: {m['home']} x {m['away']}")

    return '\n'.join(parts)


# ── Episode generation ────────────────────────────────────────────────────────

def generate_episode(source_config: dict, output_dir: str,
                     narrators: list[dict], is_first_of_day: bool = False,
                     station_name: str = 'RadioIA',
                     llm_config: dict | None = None,
                     tts_config: dict | None = None,
                     status_callback=None) -> int:
    from src.script_generator import generate_script
    from src.tts_generator import parse_script, generate_audio_files

    def _status(etapa: str, progresso: str = ''):
        if status_callback:
            status_callback(etapa, progresso)

    source_name = source_config.get('name', 'Resumo do Dia')

    data = _collect_data(source_config)

    if not any([data['clima'], data['cambio'], data['loterias'],
                data['futebol'], data['bolsa'], data['sol']]):
        raise RuntimeError("Nenhum dado disponível para gerar o episódio.")

    content = _format_data_for_prompt(data)
    _status('llm')

    llm_cfg  = llm_config or {}
    model    = source_config.get('model') or llm_cfg.get('model', 'claude-sonnet-4-6')
    api_base = llm_cfg.get('api_base')

    narrators_active = narrators[:2]
    items = [{
        'id': 'utility', 'title': source_name, 'text': content,
        'source_type': 'utility', 'source_name': source_name,
        'url': '', 'views': 0, 'comments': [], 'channel': source_name, 'published_at': '',
    }]

    script, _ = generate_script(
        items, narrators_active,
        {**source_config, 'type': 'utility'},
        is_first_of_day=is_first_of_day,
        station_name=station_name,
        model=model,
        api_base=api_base,
    )
    print(f"  {len(script.split())} palavras.\n")

    lines = parse_script(script)
    if not lines:
        raise RuntimeError("LLM retornou roteiro sem falas no formato esperado.")

    _status('tts', f'{len(lines)} falas')
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, 'temp')

    keys   = ['LOCUTOR_A', 'LOCUTOR_B']
    voices = {keys[i]: n['voice'] for i, n in enumerate(narrators_active)}
    audio_files = generate_audio_files(lines, voices, temp_dir, tts_config or {})

    _status('mixando')
    combined   = AudioSegment.empty()
    PAUSE_SAME = 150
    PAUSE_DIFF = 500
    for i, (path, line) in enumerate(zip(audio_files, lines)):
        combined += AudioSegment.from_mp3(path)
        if i < len(lines) - 1:
            pause = PAUSE_DIFF if lines[i + 1]['locutor'] != line['locutor'] else PAUSE_SAME
            combined += AudioSegment.silent(pause)

    episode_path = os.path.join(output_dir, 'episode.mp3')
    combined.export(episode_path, format='mp3', bitrate='128k',
                    tags={'title': source_name, 'artist': station_name})
    shutil.rmtree(temp_dir, ignore_errors=True)
    duration = round(len(combined) / 1000)

    # Notes for web player
    notes = []
    if data['sol']:
        s = data['sol']
        notes.append({
            'title':   f"Sol — nasce {s['sunrise']} / se põe {s['sunset']}",
            'channel': f"{s['day_length_h']}h{s['day_length_m']:02d}min de luz",
            'url': 'https://sunrise-sunset.org', 'views': 0, 'published_at': '', 'top_comments': [],
        })
    for w in data['clima']:
        notes.append({
            'title':   f"Clima em {w['city']}",
            'channel': f"{w['description'].capitalize()} · {w['temp']}°C "
                       f"(min {w['temp_min']}° / max {w['temp_max']}°) · Umidade {w['humidity']}%",
            'url': '', 'views': 0, 'published_at': '', 'top_comments': [],
        })
    for day in data['previsao']:
        rain_txt = f" · Chuva {day['rain_prob']}%" if day['rain_prob'] >= 30 else ''
        notes.append({
            'title':   f"Previsão {day['city']} — {day['label'].capitalize()}",
            'channel': f"{day['desc'].capitalize()} · {day['temp_min']}°/{day['temp_max']}°{rain_txt}",
            'url': '', 'views': 0, 'published_at': '', 'top_comments': [],
        })
    if data['bolsa'].get('pontos'):
        b   = data['bolsa']
        pct = b.get('change', 0)
        notes.append({
            'title':   f"Ibovespa: {b['pontos']:,} pts",
            'channel': f"{'Alta' if pct >= 0 else 'Baixa'} de {abs(pct):.2f}%",
            'url': '', 'views': 0, 'published_at': '', 'top_comments': [],
        })
    ft = data['futebol']
    for m in ft.get('finished', []) + ft.get('today', []) + ft.get('live', []):
        hs, as_ = m.get('home_score'), m.get('away_score')
        score_txt = f"{hs} x {as_}" if hs is not None else 'a jogar'
        notes.append({
            'title':   f"{m['home']} x {m['away']}",
            'channel': f"{ft.get('name', 'Copa')} · {score_txt}",
            'url': '', 'views': 0, 'published_at': '', 'top_comments': [],
        })
    for item in data['cambio']:
        notes.append({
            'title':   f"{item['pair']}: R$ {item['bid']:.2f}",
            'channel': _pct(item['pct_change']).capitalize(),
            'url': '', 'views': 0, 'published_at': '', 'top_comments': [],
        })
    for lot in data['loterias']:
        status = 'Acumulou' if lot['acumulado'] else f"{lot['ganhadores']} ganhador(es)"
        notes.append({
            'title':   f"{lot['name']} — Concurso {lot['numero']}",
            'channel': f"{lot['dezenas']} · {status}",
            'url': '', 'views': 0, 'published_at': '', 'top_comments': [],
        })

    meta = {
        'source_name':      source_name,
        'duration_seconds': duration,
        'videos_covered':   len(notes),
        'links':            notes,
    }
    with open(os.path.join(output_dir, 'episode.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return duration
