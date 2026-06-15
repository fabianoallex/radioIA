import json
import os
from datetime import datetime

from mcp_tools._instance import mcp
from mcp_tools._utils import PROJECT_DIR

_OPERACAO_FILE = os.path.join(PROJECT_DIR, 'OPERACAO.md')


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
