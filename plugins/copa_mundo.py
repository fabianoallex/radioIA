"""
Plugin RadioIA — Copa do Mundo 2026

Busca resultados e jogos agendados da Copa do Mundo 2026 via football-data.org v4.
Retorna um episódio com dados objetivos: dia, dia da semana, horário BRT,
estádio, cidade, fase, grupo e placar.

Referência: https://www.fifa.com/pt/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures

Para usar, adicione ao config.yaml:
  - id: copa-mundo
    type: copa_mundo
    name: "Copa do Mundo 2026"
    enabled: true
    model: claude-haiku-4-5-20251001
    settings:
      api_key_env: FOOTBALL_DATA_API_KEY
      days_lookback: 2   # dias passados para incluir resultados (default: 2)
      days_ahead: 1      # dias à frente para incluir agenda (default: 1)
"""

import os
from datetime import datetime, timedelta, timezone

import requests

BRT = timezone(timedelta(hours=-3))

_WEEKDAYS_PT = [
    'segunda-feira', 'terça-feira', 'quarta-feira',
    'quinta-feira', 'sexta-feira', 'sábado', 'domingo',
]

_MONTHS_PT = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]

_TEAM_PT = {
    'Brazil': 'Brasil', 'Germany': 'Alemanha', 'France': 'França',
    'Spain': 'Espanha', 'England': 'Inglaterra', 'Italy': 'Itália',
    'Netherlands': 'Holanda', 'Portugal': 'Portugal', 'Argentina': 'Argentina',
    'Uruguay': 'Uruguai', 'Mexico': 'México', 'United States': 'Estados Unidos',
    'USA': 'Estados Unidos', 'Japan': 'Japão', 'South Korea': 'Coreia do Sul',
    'Morocco': 'Marrocos', 'Senegal': 'Senegal', 'Australia': 'Austrália',
    'Switzerland': 'Suíça', 'Belgium': 'Bélgica', 'Croatia': 'Croácia',
    'Serbia': 'Sérvia', 'Poland': 'Polônia', 'Denmark': 'Dinamarca',
    'Austria': 'Áustria', 'Ecuador': 'Equador', 'Colombia': 'Colômbia',
    'Chile': 'Chile', 'Peru': 'Peru', 'Venezuela': 'Venezuela',
    'Bolivia': 'Bolívia', 'Paraguay': 'Paraguai', 'Canada': 'Canadá',
    'Saudi Arabia': 'Arábia Saudita', 'Iran': 'Irã', 'Qatar': 'Catar',
    'Tunisia': 'Tunísia', 'Cameroon': 'Camarões', 'Ghana': 'Gana',
    'Nigeria': 'Nigéria', "Côte d'Ivoire": 'Costa do Marfim',
    'Ivory Coast': 'Costa do Marfim', 'Egypt': 'Egito', 'Algeria': 'Argélia',
    'Wales': 'País de Gales', 'Scotland': 'Escócia', 'Turkey': 'Turquia',
    'Ukraine': 'Ucrânia', 'Czech Republic': 'República Tcheca',
    'Slovakia': 'Eslováquia', 'Romania': 'Romênia', 'Panama': 'Panamá',
    'Costa Rica': 'Costa Rica', 'Honduras': 'Honduras', 'Jamaica': 'Jamaica',
    'New Zealand': 'Nova Zelândia', 'China': 'China', 'Indonesia': 'Indonésia',
    'Albania': 'Albânia', 'Slovenia': 'Eslovênia', 'Georgia': 'Geórgia',
    'Azerbaijan': 'Azerbaijão', 'Kazakhstan': 'Cazaquistão',
    'Guatemala': 'Guatemala', 'El Salvador': 'El Salvador',
    'Trinidad and Tobago': 'Trinidad e Tobago', 'Cuba': 'Cuba',
    'Haiti': 'Haiti', 'Curaçao': 'Curaçao',
    'Iraq': 'Iraque', 'Uzbekistan': 'Uzbequistão', 'Thailand': 'Tailândia',
    'Vietnam': 'Vietnã', 'Philippines': 'Filipinas', 'Malaysia': 'Malásia',
    'Tanzania': 'Tanzânia', 'Angola': 'Angola', 'Mali': 'Mali',
    'Zambia': 'Zâmbia', 'Kenya': 'Quênia', 'Uganda': 'Uganda',
    'Zimbabwe': 'Zimbábue', 'Malawi': 'Malaui',
}

_STAGE_PT = {
    'GROUP_STAGE':      'Fase de Grupos',
    'ROUND_OF_16':      'Oitavas de Final',
    'QUARTER_FINALS':   'Quartas de Final',
    'SEMI_FINALS':      'Semifinais',
    'THIRD_PLACE':      'Disputa do 3º Lugar',
    'FINAL':            'Final',
    'PRELIMINARY_ROUND': 'Fase Preliminar',
    'PLAYOFFS':         'Play-offs',
}

_GROUP_PT = {f'GROUP_{c}': f'Grupo {c}' for c in 'ABCDEFGHIJKLMNOP'}

# Estádios da Copa do Mundo 2026 → (cidade, país)
_VENUES: dict[str, tuple[str, str]] = {
    'MetLife Stadium':              ('East Rutherford / Nova York',       'EUA'),
    'AT&T Stadium':                 ('Dallas / Arlington',                 'EUA'),
    'SoFi Stadium':                 ('Los Angeles / Inglewood',            'EUA'),
    "Levi's Stadium":               ('San Francisco / Santa Clara',        'EUA'),
    'Empower Field at Mile High':   ('Denver',                             'EUA'),
    'Arrowhead Stadium':            ('Kansas City',                        'EUA'),
    'Hard Rock Stadium':            ('Miami',                              'EUA'),
    'Mercedes-Benz Stadium':        ('Atlanta',                            'EUA'),
    'NRG Stadium':                  ('Houston',                            'EUA'),
    'Gillette Stadium':             ('Boston / Foxborough',                'EUA'),
    'Lincoln Financial Field':      ('Filadélfia',                         'EUA'),
    'BC Place':                     ('Vancouver',                          'Canadá'),
    'Estadio Akron':                ('Guadalajara',                        'México'),
    'Estadio Azteca':               ('Cidade do México',                   'México'),
}


def _team(name: str) -> str:
    return _TEAM_PT.get(name, name)


def _stage(stage: str) -> str:
    return _STAGE_PT.get(stage, stage.replace('_', ' ').title())


def _group(group: str | None) -> str:
    if not group:
        return ''
    return _GROUP_PT.get(group, group.replace('_', ' ').title())


def _fmt_date(dt: datetime) -> str:
    return f"{dt.day} de {_MONTHS_PT[dt.month - 1]}"


def _fmt_weekday(dt: datetime) -> str:
    return _WEEKDAYS_PT[dt.weekday()]


def _venue_city(venue: str | None) -> tuple[str, str]:
    if not venue:
        return '', ''
    entry = _VENUES.get(venue)
    return (venue, entry[0]) if entry else (venue, '')


def _fmt_match(m: dict, status_label: str = '') -> str:
    brt_dt = datetime.fromisoformat(
        m['utcDate'].replace('Z', '+00:00')
    ).astimezone(BRT)

    home = _team(m['homeTeam'].get('name') or m['homeTeam'].get('shortName', ''))
    away = _team(m['awayTeam'].get('name') or m['awayTeam'].get('shortName', ''))
    ft   = m.get('score', {}).get('fullTime', {})
    hs, as_ = ft.get('home'), ft.get('away')
    status  = m.get('status', '')

    stage_str = _stage(m.get('stage', ''))
    group_str = _group(m.get('group'))
    stadium, city = _venue_city(m.get('venue') or '')

    parts = [
        f"Data: {_fmt_date(brt_dt)}, {_fmt_weekday(brt_dt)}",
        f"Horário: {brt_dt.strftime('%H:%M')} (Brasília)",
    ]
    if stage_str:
        parts.append(f"Fase: {stage_str}")
    if group_str:
        parts.append(f"Grupo: {group_str}")
    parts.append(f"Jogo: {home} x {away}")
    if hs is not None and as_ is not None:
        parts.append(f"Resultado: {home} {hs} x {as_} {away}")
    elif status in ('SCHEDULED', 'TIMED'):
        parts.append('Resultado: a jogar')
    elif status == 'IN_PLAY':
        parts.append(f"Resultado: em andamento — {home} {hs} x {as_} {away}")
    if stadium:
        parts.append(f"Estádio: {stadium}")
    if city:
        parts.append(f"Local: {city}")

    return ' | '.join(parts)


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings      = source_config.get('settings') or {}
    api_key_env   = settings.get('api_key_env', 'FOOTBALL_DATA_API_KEY')
    days_lookback = int(settings.get('days_lookback', 2))
    days_ahead    = int(settings.get('days_ahead', 1))

    api_key = os.getenv(api_key_env, '')
    if not api_key:
        print(f'  [copa-mundo] {api_key_env} não encontrada — pulando.')
        return []

    now_brt   = datetime.now(BRT)
    today     = now_brt.date()
    date_from = today - timedelta(days=days_lookback)
    date_to   = today + timedelta(days=days_ahead)

    try:
        resp = requests.get(
            'https://api.football-data.org/v4/competitions/WC/matches',
            params={'dateFrom': str(date_from), 'dateTo': str(date_to)},
            headers={'X-Auth-Token': api_key},
            timeout=15,
        )
        resp.raise_for_status()
        matches = resp.json().get('matches', [])
    except Exception as e:
        print(f'  [copa-mundo] Erro na API: {e}')
        return []

    if not matches:
        print('  [copa-mundo] Nenhum jogo no período consultado.')
        return []

    past, live, today_sched, upcoming = [], [], [], []

    for m in matches:
        brt_dt     = datetime.fromisoformat(
            m['utcDate'].replace('Z', '+00:00')
        ).astimezone(BRT)
        status     = m.get('status', '')
        match_date = brt_dt.date()

        home = _team(m['homeTeam'].get('name') or m['homeTeam'].get('shortName', ''))
        away = _team(m['awayTeam'].get('name') or m['awayTeam'].get('shortName', ''))
        ft   = m.get('score', {}).get('fullTime', {})
        hs, as_ = ft.get('home'), ft.get('away')
        score_str = f"{hs}x{as_}" if hs is not None else '?'
        print(f'  [{status}] {home} {score_str} {away}  {brt_dt.strftime("%d/%m %H:%M")}')

        if status == 'IN_PLAY':
            live.append(m)
        elif status == 'FINISHED':
            past.append(m)
        elif match_date == today:
            today_sched.append(m)
        else:
            upcoming.append(m)

    sections: list[str] = []

    if live:
        sections.append('[AO VIVO]')
        sections.extend(_fmt_match(m) for m in live)

    if past:
        sections.append('[RESULTADOS RECENTES]')
        sections.extend(_fmt_match(m) for m in past)

    if today_sched:
        sections.append('[JOGOS DE HOJE]')
        sections.extend(_fmt_match(m) for m in today_sched)

    if upcoming:
        sections.append('[PRÓXIMOS JOGOS]')
        sections.extend(_fmt_match(m) for m in upcoming)

    if not sections:
        return []

    text     = '\n'.join(sections)
    today_iso = today.isoformat()
    total    = len(past) + len(live) + len(today_sched) + len(upcoming)
    print(f'  [copa-mundo] {total} jogo(s) incluído(s) no episódio.')

    return [{
        'id':           f"copa-mundo-{today_iso}",
        'title':        'Copa do Mundo 2026 — Resultados e Agenda',
        'text':         text,
        'url':          'https://www.fifa.com/pt/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures',
        'source_name':  source_config.get('name', 'Copa do Mundo 2026'),
        'source_type':  source_config.get('type', 'copa_mundo'),
        'published_at': today_iso,
        'views':        0,
        'comments':     [],
        'channel':      'Copa do Mundo 2026',
    }]
