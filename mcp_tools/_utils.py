import contextlib
import io
import json
import os
import shutil

import yaml

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_config() -> dict:
    import sys as _sys
    from src.config_schema import validate_config, ConfigError
    with open(os.path.join(PROJECT_DIR, 'config.yaml'), 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    try:
        validate_config(raw)
    except ConfigError as e:
        print(e)
        _sys.exit(1)
    return raw


def _save_config(config: dict) -> None:
    """Salva config.yaml. Observacao: comentarios no arquivo serao perdidos apos salvar."""
    for entry in config.get('schedule', []):
        t = entry.get('time')
        if isinstance(t, int):
            entry['time'] = f"{t // 60:02d}:{t % 60:02d}"
    config_path = os.path.join(PROJECT_DIR, 'config.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, indent=2)


def _capture(func, *args, **kwargs):
    """Executa func capturando stdout. Retorna (resultado, log, erro)."""
    buf = io.StringIO()
    result = None
    error = None
    try:
        with contextlib.redirect_stdout(buf):
            result = func(*args, **kwargs)
    except Exception as e:
        error = str(e)
        buf.write(f"\nERRO: {e}")
    return result, buf.getvalue(), error


def _parse_fonte(arg: str) -> tuple[str, str | None, str]:
    """'musica:3|contexto' -> ('musica', '3', 'contexto') | 'youtube' -> ('youtube', None, '')"""
    base, _, ctx = arg.partition('|')
    if ':' in base:
        sid, param = base.split(':', 1)
        return sid.strip(), param.strip(), ctx.strip()
    return base.strip(), None, ctx.strip()


def _fonte_info(s: dict, seen_ids: set) -> dict:
    return {
        'id':         s['id'],
        'nome':       s['name'],
        'tipo':       s['type'],
        'habilitada': s.get('enabled', True),
    }


def _has_audio(ep_path: str) -> bool:
    """Verifica se a pasta tem episódio (mp3 direto ou replay via audio_path)."""
    if os.path.exists(os.path.join(ep_path, 'episode.mp3')):
        return True
    meta_path = os.path.join(ep_path, 'episode.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return bool(json.load(f).get('audio_path'))
        except Exception:
            pass
    return False


def _scan_day(date_str: str) -> list[dict]:
    day_dir = os.path.join(PROJECT_DIR, 'output', date_str)
    episodes = []
    if not os.path.isdir(day_dir):
        return episodes
    for ep_folder in sorted(os.listdir(day_dir)):
        ep_path = os.path.join(day_dir, ep_folder)
        if not os.path.isdir(ep_path) or not _has_audio(ep_path):
            continue
        meta = {}
        meta_path = os.path.join(ep_path, 'episode.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        parts = ep_folder.split('_', 1)
        ep = {
            'pasta':       ep_folder,
            'horario':     parts[0],
            'fonte':       parts[1] if len(parts) > 1 else ep_folder,
            'nome':        meta.get('source_name', ''),
            'duracao_seg': meta.get('duration_seconds', 0),
            'itens':       meta.get('videos_covered', 0),
            'arquivo':     os.path.join(day_dir, ep_folder, 'episode.mp3'),
        }
        if meta.get('replay_of'):
            ep['replay_de'] = meta['replay_of']
        episodes.append(ep)
    return episodes


def _schedule_entry_key(entry: dict) -> str:
    """Chave unica de uma entrada da grade (espelha logica do scheduler.py)."""
    d    = entry.get('date', 'daily')
    t    = entry.get('time', '')
    days = ','.join(sorted(str(x) for x in entry.get('days', [])))
    if entry.get('replay_of') is not None:
        s = f"replay:{entry['replay_of']}"
    else:
        s = '+'.join(sorted(str(x) for x in entry.get('sources', [])))
    return f"{d}|{t}|{s}|{days}"


def _parse_value(s: str):
    """Converte string para bool, int, float, list/dict (JSON) ou mantém como str."""
    if isinstance(s, bool):
        return s
    if not isinstance(s, str):
        return s
    if s.lower() in ('true', 'yes', 'sim', '1'):
        return True
    if s.lower() in ('false', 'no', 'nao', 'não', '0'):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s.startswith(('[', '{')):
        try:
            return json.loads(s)
        except (ValueError, TypeError):
            pass
    return s


def _set_nested(d: dict, keys: list[str], value):
    """Define d[k1][k2]...[kn] = value criando dicts intermediarios."""
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value
