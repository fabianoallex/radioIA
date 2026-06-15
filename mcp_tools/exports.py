import json
import os
from datetime import datetime

from mcp_tools._instance import mcp
from mcp_tools._utils import PROJECT_DIR, _load_config, _scan_day


@mcp.tool()
def exportar_episodios(
    formato: str,
    data: str = '',
    pastas: list[str] = None,
) -> str:
    """
    Exporta episodios do dia como MP3 concatenado ou ZIP para o disco local.

    Args:
        formato: "concat" — MP3 unico com todos os episodios selecionados concatenados
                 "zip"    — ZIP com os episodios na estrutura de pastas (data/pasta.mp3)
                 "listar" — lista os arquivos disponiveis sem gerar exportacao
        data:    Data no formato YYYY-MM-DD. Se vazio, usa hoje.
        pastas:  Lista de subpastas a incluir (ex: ["09-00_noticias", "10-30_youtube"]).
                 Se vazio, inclui todos os episodios do dia.

    Os arquivos exportados sao salvos em output/_exports/.

    Exemplos:
        exportar_episodios("listar")
        exportar_episodios("concat")
        exportar_episodios("zip", "2026-06-10")
        exportar_episodios("concat", pastas=["09-00_noticias", "10-30_youtube"])
    """
    if not data:
        data = datetime.now().strftime('%Y-%m-%d')

    episodes = _scan_day(data)
    if not episodes:
        return json.dumps({'status': 'erro', 'mensagem': f'Nenhum episodio em {data}.'}, ensure_ascii=False)

    if pastas:
        episodes = [e for e in episodes if any(e['pasta'].startswith(p) for p in pastas)]
        if not episodes:
            return json.dumps({
                'status':   'erro',
                'mensagem': 'Nenhuma pasta encontrada com os prefixos informados.',
            }, ensure_ascii=False)

    if formato == 'listar':
        return json.dumps({
            'data':      data,
            'episodios': [{'pasta': e['pasta'], 'arquivo': e['arquivo'],
                           'nome': e['nome'], 'duracao_seg': e['duracao_seg']}
                          for e in episodes],
            'dica': 'Use exportar_episodios("concat") ou exportar_episodios("zip") para gerar o arquivo.',
        }, ensure_ascii=False, indent=2)

    def _resolve(ep: dict) -> str | None:
        if os.path.exists(ep['arquivo']):
            return ep['arquivo']
        ep_dir    = os.path.dirname(ep['arquivo'])
        meta_path = os.path.join(ep_dir, 'episode.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    ap = json.load(f).get('audio_path')
                if ap and os.path.exists(ap):
                    return ap
            except Exception:
                pass
        return None

    audio_map = [(e, _resolve(e)) for e in episodes]
    audio_map = [(e, p) for e, p in audio_map if p]

    if not audio_map:
        return json.dumps({'status': 'erro', 'mensagem': 'Nenhum arquivo de audio encontrado.'}, ensure_ascii=False)

    export_dir = os.path.join(PROJECT_DIR, 'output', '_exports')
    os.makedirs(export_dir, exist_ok=True)

    config     = _load_config()
    radio_name = config.get('radio', {}).get('name', 'RadioIA')
    safe_name  = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in radio_name.replace(' ', '_')).strip('_')

    if formato == 'concat':
        try:
            from pydub import AudioSegment
            combined = AudioSegment.empty()
            for _, p in audio_map:
                combined += AudioSegment.from_mp3(p)
            filename = f"{safe_name}_{data}.mp3"
            out_path = os.path.join(export_dir, filename)
            combined.export(out_path, format='mp3', bitrate='128k')
            return json.dumps({
                'status':     'ok',
                'formato':    'concat',
                'data':       data,
                'episodios':  len(audio_map),
                'arquivo':    out_path,
                'tamanho_mb': round(os.path.getsize(out_path) / 1024 / 1024, 1),
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({'status': 'erro', 'mensagem': str(e)}, ensure_ascii=False)

    if formato == 'zip':
        import zipfile
        filename = f"{safe_name}_{data}.zip"
        out_path = os.path.join(export_dir, filename)
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for e, p in audio_map:
                zf.write(p, f"{data}/{e['pasta']}.mp3")
        return json.dumps({
            'status':     'ok',
            'formato':    'zip',
            'data':       data,
            'episodios':  len(audio_map),
            'arquivo':    out_path,
            'tamanho_mb': round(os.path.getsize(out_path) / 1024 / 1024, 1),
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        'status':   'erro',
        'mensagem': f"Formato '{formato}' invalido. Use: concat | zip | listar",
    }, ensure_ascii=False)
