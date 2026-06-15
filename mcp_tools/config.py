import json
import os

from mcp_tools._instance import mcp
from mcp_tools._utils import (
    PROJECT_DIR,
    _load_config,
    _save_config,
    _parse_value,
    _set_nested,
)


@mcp.tool()
def configurar_fonte(id_fonte: str, campo: str, valor: str) -> str:
    """
    Altera um campo de uma fonte de conteudo no config.yaml.
    Operacao mais comum: habilitar ou desabilitar uma fonte.

    ATENCAO: salvar o config reformata o YAML e perde os comentarios do arquivo.

    Args:
        id_fonte: ID da fonte a alterar (ex: youtube, noticias, musica, horoscopo).
        campo:    Campo a alterar. Exemplos:
                  "enabled"  — true/false para habilitar/desabilitar
                  "name"     — nome exibido na programacao
                  "model"    — modelo LLM a usar (ex: claude-haiku-4-5-20251001)
        valor:    Novo valor (string — sera convertido para bool/int se aplicavel).
                  Para enabled: "true" ou "false".

    Exemplos:
        configurar_fonte("musica", "enabled", "true")
        configurar_fonte("youtube", "model", "claude-haiku-4-5-20251001")
        configurar_fonte("noticias", "name", "Noticias Gerais")
    """
    config  = _load_config()
    sources = config.get('sources', [])
    idx     = next((i for i, s in enumerate(sources) if s['id'] == id_fonte), None)

    if idx is None:
        ids = [s['id'] for s in sources]
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Fonte '{id_fonte}' nao encontrada.",
            'fontes_disponiveis': ids,
        }, ensure_ascii=False, indent=2)

    valor_convertido = _parse_value(valor)
    valor_anterior   = sources[idx].get(campo, '<nao definido>')

    sources[idx][campo] = valor_convertido
    config['sources']   = sources
    _save_config(config)

    return json.dumps({
        'status':         'ok',
        'fonte':          id_fonte,
        'campo':          campo,
        'valor_anterior': valor_anterior,
        'valor_novo':     valor_convertido,
        'aviso':          'config.yaml foi reformatado — comentarios originais foram perdidos.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def adicionar_fonte(id_fonte: str, tipo: str, nome: str, extras: str = '{}') -> str:
    """
    Adiciona uma nova fonte de conteudo ao config.yaml.

    Args:
        id_fonte: Identificador unico da fonte (ex: bom-dia, noticias-tech, minha-musica).
                  Nao pode conflitar com fontes ja existentes.
        tipo:     Tipo da fonte. Valores validos:
                  "combined"  — agrega fetch() de multiplas sub-fontes em um episodio unico.
                                Requer "sources" em extras: lista de IDs de fontes existentes.
                                Sub-fontes incompativeis (utility, music, spot) sao ignoradas.
                  "rss"       — leitor de feeds RSS. Requer "feeds" em extras.
                  "youtube"   — canal(is) do YouTube. Requer "channels" em extras.
                  "utility"   — clima, cambio, loterias, futebol (via LLM).
                  "music"     — bloco musical (jamendo ou local).
                  "clipping"  — agregador de noticias por topico.
                  "horoscopo" — horoscopo diario.
                  "podcast"   — feed de podcast.
                  "efemerides", "quiz", "reddit", "receitas", "filmes", "filmes-cartaz",
                  "concursos", "biblia", "whatsapp"
        nome:     Nome exibido na programacao (ex: "Bom Dia MT", "Noticias de Tecnologia").
        extras:   JSON com campos adicionais da fonte. Exemplos por tipo:

                  combined:
                    {"sources": ["utilidades", "noticias", "youtube"], "model": "claude-haiku-4-5-20251001", "context": "tom matinal, animado"}

                  rss:
                    {"feeds": [{"url": "https://g1.globo.com/rss/g1/", "name": "G1"}], "settings": {"max_items_total": 5}}

                  youtube:
                    {"channels": [{"id": "UCaGmdJSSiR7fkh2A-c6emsA", "name": "G1"}]}

                  utility:
                    {"settings": {"weather": {"enabled": true, "cities": ["Cuiaba"]}, "finance": {"enabled": true}, "lottery": {"enabled": false}}}

                  music (jamendo):
                    {"settings": {"num_tracks": 3, "source": "jamendo", "jamendo": {"api_key_env": "JAMENDO_CLIENT_ID", "tags": "jazz"}}}

    Exemplos:
        adicionar_fonte("bom-dia", "combined", "Bom Dia MT",
                        '{"sources": ["utilidades", "noticias", "youtube"], "model": "claude-haiku-4-5-20251001"}')
        adicionar_fonte("noticias-tech", "rss", "Tecnologia",
                        '{"feeds": [{"url": "https://www.theverge.com/rss/index.xml", "name": "The Verge"}]}')
    """
    config  = _load_config()
    sources = config.get('sources', [])

    if any(s['id'] == id_fonte for s in sources):
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Fonte '{id_fonte}' ja existe. Use configurar_fonte() para alterar campos.",
        }, ensure_ascii=False, indent=2)

    tipos_validos = {
        'combined', 'rss', 'youtube', 'utility', 'music', 'clipping',
        'horoscopo', 'podcast', 'efemerides', 'quiz', 'reddit', 'receitas',
        'filmes', 'filmes-cartaz', 'concursos', 'biblia', 'whatsapp', 'url',
    }
    if tipo not in tipos_validos:
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Tipo '{tipo}' invalido.",
            'tipos_validos': sorted(tipos_validos),
        }, ensure_ascii=False, indent=2)

    try:
        campos_extras = json.loads(extras) if extras.strip() else {}
    except json.JSONDecodeError as e:
        return json.dumps({
            'status':   'erro',
            'mensagem': f"extras nao e um JSON valido: {e}",
        }, ensure_ascii=False, indent=2)

    if tipo == 'combined' and 'sources' not in campos_extras:
        return json.dumps({
            'status':   'erro',
            'mensagem': "Tipo 'combined' requer o campo 'sources' em extras: lista de IDs de sub-fontes.",
            'exemplo':  '{"sources": ["utilidades", "noticias", "youtube"]}',
        }, ensure_ascii=False, indent=2)

    nova_fonte = {
        'id':      id_fonte,
        'type':    tipo,
        'name':    nome,
        'enabled': True,
        **campos_extras,
    }

    sources.append(nova_fonte)
    config['sources'] = sources
    _save_config(config)

    return json.dumps({
        'status':   'ok',
        'mensagem': f"Fonte '{id_fonte}' adicionada com sucesso.",
        'fonte':    nova_fonte,
        'dica':     'Use configurar_fonte() para ajustar campos individuais depois, ou gerar_episodios(["' + id_fonte + '"]) para testar.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def atualizar_config(caminho: str, valor: str) -> str:
    """
    Atualiza qualquer valor no config.yaml usando notacao de ponto.
    Para alterar fontes, prefira configurar_fonte() que e mais seguro e especifico.

    ATENCAO: salvar o config reformata o YAML e perde os comentarios do arquivo.

    Args:
        caminho: Caminho com pontos ate o valor. Exemplos:
                 "radio.name"          — nome da radio
                 "llm.model"           — modelo LLM padrao
                 "vinheta.voice"       — voz das vinhetas
                 "vinheta.rate"        — velocidade das vinhetas (ex: +20%)
                 "announcements.enabled" — avisos entre musicas (true/false)
                 "radio.background_volume_db" — volume da musica de fundo
        valor:  Novo valor como string (convertido automaticamente para bool/int se aplicavel).

    Exemplos:
        atualizar_config("radio.name", "Minha Radio Genial")
        atualizar_config("llm.model", "claude-haiku-4-5-20251001")
        atualizar_config("vinheta.voice", "pt-BR-AntonioNeural")
    """
    config = _load_config()
    chaves = caminho.split('.')

    cursor = config
    for k in chaves[:-1]:
        if not isinstance(cursor, dict) or k not in cursor:
            return json.dumps({
                'status':   'erro',
                'mensagem': f"Caminho '{caminho}' invalido — '{k}' nao encontrado.",
            }, ensure_ascii=False, indent=2)
        cursor = cursor[k]

    valor_anterior   = cursor.get(chaves[-1], '<nao definido>') if isinstance(cursor, dict) else '<nao definido>'
    valor_convertido = _parse_value(valor)

    _set_nested(config, chaves, valor_convertido)
    _save_config(config)

    return json.dumps({
        'status':         'ok',
        'caminho':        caminho,
        'valor_anterior': valor_anterior,
        'valor_novo':     valor_convertido,
        'aviso':          'config.yaml foi reformatado — comentarios originais foram perdidos.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def adicionar_grade(
    time: str,
    sources: list[str] = None,
    label: str = '',
    slot_id: int = None,
    date: str = '',
    days: list[str] = None,
    replay_of: int = None,
) -> str:
    """
    Adiciona uma nova entrada na grade de programacao do config.yaml.

    ATENCAO: salvar o config reformata o YAML e perde os comentarios do arquivo.

    Args:
        time:      Horario no formato HH:MM (ex: "14:30").
        sources:   Lista de IDs de fontes (ex: ["noticias", "tecnologia"]).
                   Obrigatorio se replay_of nao for informado.
        label:     Descricao da entrada (ex: "Noticias da tarde").
        slot_id:   ID numerico para permitir replay posterior deste episodio.
        date:      Data no formato YYYY-MM-DD para entrada pontual (so roda nessa data).
                   Omitir = entrada diaria.
        days:      Lista de dias da semana (ex: ["mon","tue","wed","thu","fri"]).
                   Omitir = todos os dias.
        replay_of: ID do slot a repetir (em vez de gerar novo episodio).

    Exemplos:
        adicionar_grade("16:00", ["noticias"], "Noticias da tarde")
        adicionar_grade("09:00", ["copa"], "Copa do Mundo", date="2026-07-14")
        adicionar_grade("18:00", replay_of=3, label="Quiz (noite)")
    """
    if not time:
        return json.dumps({'status': 'erro', 'mensagem': 'Parametro time e obrigatorio.'}, ensure_ascii=False)

    if sources is None and replay_of is None:
        return json.dumps({'status': 'erro', 'mensagem': 'Informe sources ou replay_of.'}, ensure_ascii=False)

    entry: dict = {'time': time}
    if label:
        entry['label'] = label
    if date:
        entry['date'] = date
    if days:
        entry['days'] = days
    if replay_of is not None:
        entry['replay_of'] = replay_of
    elif sources:
        entry['sources'] = sources
        if slot_id is not None:
            entry['slot_id'] = slot_id

    config   = _load_config()
    schedule = config.get('schedule', [])
    schedule.append(entry)
    schedule.sort(key=lambda e: (e.get('date', '9999'), e.get('time', '')))
    config['schedule'] = schedule
    _save_config(config)

    return json.dumps({
        'status':         'ok',
        'entrada':        entry,
        'total_entradas': len(schedule),
        'aviso':          'config.yaml foi reformatado — comentarios originais foram perdidos.',
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def remover_grade(time: str, label: str = '') -> str:
    """
    Remove entradas da grade de programacao do config.yaml.

    ATENCAO: salvar o config reformata o YAML e perde os comentarios do arquivo.

    Args:
        time:  Horario da entrada a remover (formato HH:MM).
               Se houver multiplas entradas no mesmo horario, todas serao removidas
               a menos que 'label' seja informado para filtrar.
        label: Label para filtrar quando ha multiplas entradas no mesmo horario.
               Se vazio, remove todas as entradas do horario informado.

    Exemplos:
        remover_grade("16:00")                     — remove todas as entradas das 16:00
        remover_grade("09:30", "Noticias da manha") — remove so a entrada especifica
    """
    config   = _load_config()
    schedule = config.get('schedule', [])

    removidas = [
        e for e in schedule
        if e.get('time') == time and (not label or e.get('label', '') == label)
    ]
    schedule = [
        e for e in schedule
        if not (e.get('time') == time and (not label or e.get('label', '') == label))
    ]

    if not removidas:
        entradas_no_horario = [e for e in config.get('schedule', []) if e.get('time') == time]
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Nenhuma entrada encontrada para time='{time}'" + (f" label='{label}'" if label else '') + '.',
            'entradas_no_horario': entradas_no_horario,
        }, ensure_ascii=False, indent=2)

    config['schedule'] = schedule
    _save_config(config)

    return json.dumps({
        'status':          'ok',
        'removidas':       removidas,
        'total_removidas': len(removidas),
        'total_restantes': len(schedule),
        'aviso':           'config.yaml foi reformatado — comentarios originais foram perdidos.',
    }, ensure_ascii=False, indent=2)
