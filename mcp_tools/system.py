import json
import os
import shutil
import sys
from datetime import datetime, timedelta

from mcp_tools._instance import mcp
from mcp_tools._utils import PROJECT_DIR, _load_config

_PID_FILE = os.path.join(PROJECT_DIR, 'scheduler.pid')


def _scheduler_pid() -> int | None:
    """Retorna o PID salvo em scheduler.pid, ou None se nao existir."""
    if not os.path.exists(_PID_FILE):
        return None
    try:
        with open(_PID_FILE, 'r') as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def _process_alive(pid: int) -> bool:
    """Verifica se um processo com o PID dado esta rodando."""
    try:
        if sys.platform == 'win32':
            import subprocess as _sp
            r = _sp.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                        capture_output=True, text=True)
            return str(pid) in r.stdout
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _scheduler_status() -> dict:
    """Retorna dict com estado real do scheduler."""
    pid = _scheduler_pid()
    if pid and _process_alive(pid):
        state_path = os.path.join(PROJECT_DIR, 'scheduler_state.json')
        age_s = None
        if os.path.exists(state_path):
            age_s = int(datetime.now().timestamp() - os.path.getmtime(state_path))
        return {
            'ativo':           True,
            'pid':             pid,
            'ultimo_tick_seg': age_s,
            'dica':            'Use controlar_scheduler("stop") para encerrar.',
        }

    if os.path.exists(_PID_FILE):
        os.remove(_PID_FILE)

    state_path = os.path.join(PROJECT_DIR, 'scheduler_state.json')
    if os.path.exists(state_path):
        age_s = int(datetime.now().timestamp() - os.path.getmtime(state_path))
        if age_s < 90:
            return {
                'ativo':           True,
                'pid':             None,
                'ultimo_tick_seg': age_s,
                'aviso':           'Processo ativo detectado por timestamp (sem PID file — iniciado fora do MCP).',
                'dica':            'Use controlar_scheduler("stop") com cuidado — sem PID nao e possivel encerrar automaticamente.',
            }

    return {
        'ativo': False,
        'pid':   None,
        'dica':  'Use controlar_scheduler("start") para iniciar.',
    }


@mcp.tool()
def controlar_scheduler(acao: str) -> str:
    """
    Inicia, para ou verifica o status do scheduler da RadioIA.

    Args:
        acao: "start"  — inicia o scheduler em background e salva o PID em scheduler.pid
              "stop"   — encerra o scheduler pelo PID salvo
              "status" — verifica se o scheduler esta rodando

    O scheduler executa a grade configurada em config.yaml automaticamente.
    Os logs sao salvos em scheduler.log na raiz do projeto.

    Exemplos:
        controlar_scheduler("status")
        controlar_scheduler("start")
        controlar_scheduler("stop")
    """
    acao = acao.strip().lower()

    if acao == 'status':
        return json.dumps({'acao': 'status', **_scheduler_status()}, ensure_ascii=False, indent=2)

    if acao == 'start':
        status = _scheduler_status()
        if status['ativo']:
            return json.dumps({
                'acao':     'start',
                'status':   'ja_rodando',
                'pid':      status.get('pid'),
                'mensagem': 'Scheduler ja esta ativo. Use controlar_scheduler("stop") para encerrar antes de reiniciar.',
            }, ensure_ascii=False, indent=2)

        if os.path.exists(_PID_FILE):
            os.remove(_PID_FILE)

        log_path = os.path.join(PROJECT_DIR, 'scheduler.log')
        log_file = open(log_path, 'a', encoding='utf-8')

        if sys.platform == 'win32':
            import subprocess as _sp
            _sp.Popen(
                [sys.executable, os.path.join(PROJECT_DIR, 'scheduler.py')],
                stdout=log_file,
                stderr=log_file,
                cwd=PROJECT_DIR,
                creationflags=_sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS,
            )
        else:
            import subprocess as _sp
            _sp.Popen(
                [sys.executable, os.path.join(PROJECT_DIR, 'scheduler.py')],
                stdout=log_file,
                stderr=log_file,
                cwd=PROJECT_DIR,
                start_new_session=True,
            )

        import time as _time
        for _ in range(20):
            _time.sleep(0.25)
            if os.path.exists(_PID_FILE):
                break

        pid = _scheduler_pid()
        return json.dumps({
            'acao':     'start',
            'status':   'iniciado' if pid else 'iniciado_sem_pid',
            'pid':      pid,
            'log':      log_path,
            'mensagem': f'Scheduler iniciado (PID {pid}). Logs em scheduler.log.' if pid
                        else 'Scheduler iniciado mas PID nao confirmado ainda — verifique scheduler.log.',
        }, ensure_ascii=False, indent=2)

    if acao == 'stop':
        pid = _scheduler_pid()

        if not pid:
            status = _scheduler_status()
            if not status['ativo']:
                return json.dumps({
                    'acao':     'stop',
                    'status':   'nao_estava_rodando',
                    'mensagem': 'Scheduler nao estava ativo.',
                }, ensure_ascii=False, indent=2)
            return json.dumps({
                'acao':     'stop',
                'status':   'erro',
                'mensagem': 'Scheduler parece ativo mas nao ha PID file (foi iniciado fora do MCP). Encerre manualmente.',
            }, ensure_ascii=False, indent=2)

        if not _process_alive(pid):
            os.remove(_PID_FILE)
            return json.dumps({
                'acao':     'stop',
                'status':   'ja_parado',
                'mensagem': f'Processo {pid} ja havia encerrado. PID file removido.',
            }, ensure_ascii=False, indent=2)

        try:
            if sys.platform == 'win32':
                import subprocess as _sp
                _sp.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
        except Exception as e:
            return json.dumps({
                'acao':     'stop',
                'status':   'erro',
                'pid':      pid,
                'mensagem': str(e),
            }, ensure_ascii=False, indent=2)

        if os.path.exists(_PID_FILE):
            os.remove(_PID_FILE)

        return json.dumps({
            'acao':     'stop',
            'status':   'encerrado',
            'pid':      pid,
            'mensagem': f'Scheduler (PID {pid}) encerrado.',
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':   'erro',
        'mensagem': f"Acao '{acao}' invalida. Use: start | stop | status",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def limpar_output(dias_manter: int = 7, preview: bool = True) -> str:
    """
    Remove episodios antigos da pasta output para liberar espaco em disco.

    Args:
        dias_manter: Numero de dias recentes a manter. Default: 7.
                     Pastas com datas mais antigas serao removidas.
        preview:     Se True (padrao), apenas lista o que seria removido sem deletar.
                     Use preview=False para realmente deletar os arquivos.

    Exemplos:
        limpar_output()                    — lista o que seria removido (seguro)
        limpar_output(dias_manter=30)      — lista pastas mais antigas que 30 dias
        limpar_output(dias_manter=7, preview=False) — deleta de verdade
    """
    output_dir = os.path.join(PROJECT_DIR, 'output')
    if not os.path.exists(output_dir):
        return json.dumps({'status': 'ok', 'mensagem': 'Pasta output nao existe.'}, ensure_ascii=False)

    cutoff = (datetime.now() - timedelta(days=dias_manter)).strftime('%Y-%m-%d')

    datas = sorted([
        d for d in os.listdir(output_dir)
        if os.path.isdir(os.path.join(output_dir, d)) and len(d) == 10 and d[:4].isdigit()
    ])

    para_remover = [d for d in datas if d < cutoff]
    para_manter  = [d for d in datas if d >= cutoff]

    def _dir_size(path: str) -> int:
        return sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(path)
            for f in files
        )

    detalhes = []
    total_bytes = 0
    for d in para_remover:
        p = os.path.join(output_dir, d)
        sz = _dir_size(p)
        total_bytes += sz
        detalhes.append({'data': d, 'tamanho_mb': round(sz / 1024 / 1024, 1)})

    if preview:
        return json.dumps({
            'status':       'preview',
            'cutoff':       cutoff,
            'dias_manter':  dias_manter,
            'para_remover': detalhes,
            'para_manter':  para_manter,
            'espaco_mb':    round(total_bytes / 1024 / 1024, 1),
            'mensagem':     f"Simulacao: {len(para_remover)} pasta(s) seriam removidas ({round(total_bytes/1024/1024,1)} MB). "
                            f"Use preview=False para confirmar.",
        }, ensure_ascii=False, indent=2)

    removidas = []
    erros = []
    for d in para_remover:
        p = os.path.join(output_dir, d)
        try:
            shutil.rmtree(p)
            removidas.append(d)
        except Exception as e:
            erros.append({'data': d, 'erro': str(e)})

    return json.dumps({
        'status':             'ok',
        'removidas':          removidas,
        'total_removidas':    len(removidas),
        'espaco_liberado_mb': round(total_bytes / 1024 / 1024, 1),
        'mantidas':           para_manter,
        'erros':              erros,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def testar_tts(texto: str, voz: str = '') -> str:
    """
    Gera um arquivo de audio de teste usando o TTS configurado (edge-tts por padrao).
    Util para verificar se o TTS esta funcionando e ouvir como uma voz soa.

    Args:
        texto: Texto a sintetizar (ex: "Bem-vindos a RadioIA, sua radio personalizada!").
        voz:   Nome da voz edge-tts a usar. Se vazio, usa a voz da vinheta configurada.
               Vozes pt-BR disponiveis:
               - pt-BR-ThalitaMultilingualNeural (feminina, padrao narradora Ana)
               - pt-BR-AntonioNeural (masculina, narrador Carlos)
               - pt-BR-FranciscaNeural (feminina, vinhetas)

    O arquivo gerado e salvo em output/tts_test.mp3.
    """
    import asyncio
    import edge_tts

    config = _load_config()

    if not voz:
        voz = config.get('vinheta', {}).get('voice', 'pt-BR-FranciscaNeural')

    output_path = os.path.join(PROJECT_DIR, 'output', 'tts_test.mp3')
    os.makedirs(os.path.join(PROJECT_DIR, 'output'), exist_ok=True)

    async def _synth():
        comm = edge_tts.Communicate(texto, voz)
        await comm.save(output_path)

    try:
        asyncio.run(_synth())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_synth())
        loop.close()

    if not os.path.exists(output_path):
        return json.dumps({'status': 'erro', 'mensagem': 'Arquivo nao gerado.'}, ensure_ascii=False)

    size_kb = round(os.path.getsize(output_path) / 1024, 1)

    return json.dumps({
        'status':     'ok',
        'voz':        voz,
        'texto':      texto,
        'arquivo':    output_path,
        'tamanho_kb': size_kb,
        'mensagem':   f"Audio gerado com sucesso. Acesse em http://localhost:5000 ou abra o arquivo diretamente.",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def deletar_episodio(pasta: str, data: str = '') -> str:
    """
    Remove a pasta de um episodio especifico do output/.
    Use ler_episodio() primeiro para confirmar o conteudo antes de deletar.

    Args:
        pasta: Nome ou prefixo parcial da pasta do episodio. Exemplos:
               "09-30_youtube"  — episodio exato
               "09-30"          — qualquer episodio das 09:30
               "youtube"        — todos os episodios de youtube do dia
        data:  Data no formato YYYY-MM-DD. Se vazio, usa hoje.

    Retorna a lista de pastas removidas e o espaco liberado.
    """
    if not data:
        data = datetime.now().strftime('%Y-%m-%d')

    day_dir = os.path.join(PROJECT_DIR, 'output', data)
    if not os.path.isdir(day_dir):
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Nenhum episodio encontrado para {data}.",
        }, ensure_ascii=False, indent=2)

    candidatos = [
        f for f in sorted(os.listdir(day_dir))
        if pasta.lower() in f.lower() and os.path.isdir(os.path.join(day_dir, f))
    ]

    if not candidatos:
        return json.dumps({
            'status':   'erro',
            'mensagem': f"Nenhuma pasta com '{pasta}' em {data}.",
            'pastas_disponiveis': [
                f for f in sorted(os.listdir(day_dir))
                if os.path.isdir(os.path.join(day_dir, f))
            ],
        }, ensure_ascii=False, indent=2)

    removidas   = []
    erros       = []
    bytes_total = 0

    for folder in candidatos:
        ep_path = os.path.join(day_dir, folder)
        try:
            sz = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(ep_path)
                for f in files
            )
            shutil.rmtree(ep_path)
            removidas.append({'pasta': folder, 'tamanho_kb': round(sz / 1024, 1)})
            bytes_total += sz
        except Exception as e:
            erros.append({'pasta': folder, 'erro': str(e)})

    return json.dumps({
        'status':              'ok' if removidas else 'erro',
        'data':                data,
        'removidas':           removidas,
        'total_removidas':     len(removidas),
        'espaco_liberado_kb':  round(bytes_total / 1024, 1),
        'erros':               erros,
    }, ensure_ascii=False, indent=2)
