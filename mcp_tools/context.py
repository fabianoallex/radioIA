import json
import os
from datetime import datetime

from mcp_tools._instance import mcp
from mcp_tools._utils import PROJECT_DIR, _load_config, _scan_day, _schedule_entry_key
from mcp_tools.system import _scheduler_status

_OPERACAO_FILE = os.path.join(PROJECT_DIR, 'OPERACAO.md')


@mcp.tool()
def briefing() -> str:
    """
    Retorna um snapshot operacional completo para orientar o inicio de uma sessao.
    Inclui: status do sistema, configuracao da radio, episodios de hoje,
    proximos agendamentos e notas operacionais registradas em sessoes anteriores.

    Chame este tool PRIMEIRO em qualquer nova sessao antes de operar a radio.
    """
    resultado: dict = {}

    config = _load_config()
    radio  = config.get('radio', {})
    resultado['radio'] = {
        'nome':            radio.get('name', 'RadioIA'),
        'llm_model':       config.get('llm', {}).get('model', ''),
        'tts_provider':    config.get('tts', {}).get('provider', 'edge_tts'),
        'narradores':      [n.get('name') for n in config.get('narrators', [])],
        'fontes_ativas':   [s['id'] for s in config.get('sources', []) if s.get('enabled', True)],
        'fontes_inativas': [s['id'] for s in config.get('sources', []) if not s.get('enabled', True)],
        'spots':           [s['id'] for s in (config.get('spots') or [])],
    }

    resultado['scheduler'] = _scheduler_status()

    import urllib.request
    player_ativo = False
    try:
        urllib.request.urlopen('http://localhost:5000', timeout=2)
        player_ativo = True
    except Exception:
        pass
    resultado['player'] = {'ativo': player_ativo, 'url': 'http://localhost:5000'}

    faltando = [
        k for k in ('ANTHROPIC_API_KEY', 'YOUTUBE_API_KEY')
        if not os.environ.get(k)
    ]
    resultado['api_keys_faltando'] = faltando

    hoje = datetime.now().strftime('%Y-%m-%d')
    eps_hoje  = _scan_day(hoje)
    total_dur = sum(e['duracao_seg'] for e in eps_hoje)
    resultado['hoje'] = {
        'data':            hoje,
        'total_episodios': len(eps_hoje),
        'duracao_total':   f"{total_dur // 3600}h {(total_dur % 3600) // 60}m",
        'ultimo_episodio': eps_hoje[-1]['pasta'] if eps_hoje else None,
    }

    now_time = datetime.now().strftime('%H:%M')
    state_path = os.path.join(PROJECT_DIR, 'scheduler_state.json')
    state = {}
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
    completed_today = set(state.get('completed_today', {}).keys())

    proximos = []
    for entry in config.get('schedule', []):
        if (not entry.get('date')
                and entry.get('time', '') >= now_time
                and f"{hoje}|{_schedule_entry_key(entry)}" not in completed_today):
            proximos.append({
                'time':    entry['time'],
                'label':   entry.get('label', ''),
                'sources': entry.get('sources', [f"replay:{entry['replay_of']}"
                                                  if entry.get('replay_of') is not None
                                                  else '']),
            })
            if len(proximos) >= 5:
                break
    resultado['proximos_agendamentos'] = proximos

    history_path = os.path.join(PROJECT_DIR, 'history.json')
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            h = json.load(f)
        resultado['historico'] = {
            'itens_vistos':    len(h.get('seen_ids', [])),
            'episodios_total': len(h.get('episodes', [])),
        }

    if os.path.exists(_OPERACAO_FILE):
        with open(_OPERACAO_FILE, 'r', encoding='utf-8') as f:
            resultado['notas_operacionais'] = f.read()
    else:
        resultado['notas_operacionais'] = (
            'Nenhuma nota registrada ainda. '
            'Use registrar_nota("texto", "categoria") para registrar conhecimento operacional.'
        )

    resultado['dica'] = (
        'Para registrar aprendizados desta sessao, use registrar_nota(). '
        'Essas notas ficam no projeto e estao disponiveis em qualquer sessao futura.'
    )

    return json.dumps(resultado, ensure_ascii=False, indent=2)


@mcp.tool()
def registrar_nota(nota: str, categoria: str = 'geral') -> str:
    """
    Registra uma nota operacional em OPERACAO.md para persistir conhecimento entre sessoes.
    Use para documentar: quirks descobertos, convencoes adotadas, bugs corrigidos,
    parametros que funcionam bem ou mal, decisoes de configuracao.

    O arquivo fica no projeto e e lido pelo briefing() em qualquer sessao futura.

    Args:
        nota:      Texto da nota. Seja especifico e acionavel.
                   Exemplos:
                   "Clipping com topicos muito longos (+60 chars) retorna poucos resultados"
                   "Scheduler iniciado via MCP precisa de restart apos alteracoes no config.yaml"
                   "Fonte copa funcionando bem com max_videos_total: 5"
        categoria: Categoria para organizar as notas. Sugestoes:
                   "quirk"      — comportamentos inesperados ou limitacoes conhecidas
                   "convencao"  — padroes adotados neste projeto
                   "config"     — decisoes de configuracao importantes
                   "bug"        — bugs conhecidos ou corrigidos
                   "dica"       — dicas de uso eficiente
                   "geral"      — sem categoria especifica (padrao)
    """
    if not nota.strip():
        return json.dumps({'status': 'erro', 'mensagem': 'Nota nao pode ser vazia.'}, ensure_ascii=False)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    linha = f"- **[{categoria}]** {nota.strip()} *(registrado em {timestamp})*\n"

    if os.path.exists(_OPERACAO_FILE):
        with open(_OPERACAO_FILE, 'r', encoding='utf-8') as f:
            conteudo = f.read()
    else:
        conteudo = (
            "# OPERACAO.md — Notas Operacionais RadioIA\n\n"
            "Conhecimento acumulado entre sessoes do agente MCP.\n"
            "Lido automaticamente pelo `briefing()` no inicio de cada sessao.\n\n"
        )

    with open(_OPERACAO_FILE, 'a', encoding='utf-8') as f:
        if not conteudo.strip().endswith('\n\n'):
            f.write('\n')
        f.write(linha)

    return json.dumps({
        'status':    'ok',
        'nota':      nota.strip(),
        'categoria': categoria,
        'arquivo':   _OPERACAO_FILE,
        'mensagem':  'Nota registrada. Sera incluida no briefing() de sessoes futuras.',
    }, ensure_ascii=False, indent=2)
