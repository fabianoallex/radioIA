"""Lógica de sistema para a Admin API — sem dependência do módulo MCP."""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).parent.parent.parent

_PLAYER_PORT = int(os.environ.get("PLAYER_PORT", 5000))


def _local_now() -> datetime:
    """Retorna datetime atual no fuso configurado em radio.utc_offset do config.yaml."""
    try:
        cfg_path = PROJECT_DIR / "config.yaml"
        with open(cfg_path, 'r', encoding='utf-8') as _f:
            _cfg = yaml.safe_load(_f) or {}
        offset = int((_cfg.get('radio') or {}).get('utc_offset', 0))
    except Exception:
        offset = 0
    return datetime.utcnow() + timedelta(hours=offset)


# ── config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    config_path = PROJECT_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── scheduler ─────────────────────────────────────────────────────────────────

_PID_FILE = PROJECT_DIR / "scheduler.pid"


def _read_pid() -> int | None:
    if not _PID_FILE.exists():
        return None
    try:
        return int(_PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def _process_alive(pid: int) -> bool:
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True,
            )
            return str(pid) in r.stdout
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def get_scheduler_status() -> dict:
    pid = _read_pid()
    state_path = PROJECT_DIR / "scheduler_state.json"

    if pid and _process_alive(pid):
        age_s = None
        if state_path.exists():
            age_s = int(datetime.now().timestamp() - state_path.stat().st_mtime)
        return {"ativo": True, "pid": pid, "ultimo_tick_seg": age_s}

    if _PID_FILE.exists():
        _PID_FILE.unlink(missing_ok=True)

    if state_path.exists():
        age_s = int(datetime.now().timestamp() - state_path.stat().st_mtime)
        if age_s < 90:
            return {"ativo": True, "pid": None, "ultimo_tick_seg": age_s}

    return {"ativo": False, "pid": None, "ultimo_tick_seg": None}


def start_scheduler() -> dict:
    status = get_scheduler_status()
    if status["ativo"]:
        return {"status": "ja_rodando", "pid": status.get("pid")}

    if _PID_FILE.exists():
        _PID_FILE.unlink(missing_ok=True)

    log_path = PROJECT_DIR / "scheduler.log"
    log_file = open(log_path, "a", encoding="utf-8")

    scheduler_py = PROJECT_DIR / "scheduler.py"

    if sys.platform == "win32":
        subprocess.Popen(
            [sys.executable, str(scheduler_py)],
            stdout=log_file, stderr=log_file,
            cwd=str(PROJECT_DIR),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        subprocess.Popen(
            [sys.executable, str(scheduler_py)],
            stdout=log_file, stderr=log_file,
            cwd=str(PROJECT_DIR),
            start_new_session=True,
        )

    import time
    for _ in range(20):
        time.sleep(0.25)
        if _PID_FILE.exists():
            break

    pid = _read_pid()
    return {"status": "iniciado", "pid": pid}


def stop_scheduler() -> dict:
    pid = _read_pid()
    if not pid:
        status = get_scheduler_status()
        if not status["ativo"]:
            return {"status": "nao_estava_rodando"}
        return {"status": "erro", "mensagem": "Sem PID file — encerre manualmente."}

    if not _process_alive(pid):
        _PID_FILE.unlink(missing_ok=True)
        return {"status": "ja_parado", "pid": pid}

    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        return {"status": "erro", "pid": pid, "mensagem": str(e)}

    _PID_FILE.unlink(missing_ok=True)
    return {"status": "encerrado", "pid": pid}


# ── player ────────────────────────────────────────────────────────────────────

def get_player_status() -> dict:
    url = f"http://localhost:{_PLAYER_PORT}"
    try:
        urllib.request.urlopen(url, timeout=2)
        return {"ativo": True, "url": url}
    except Exception:
        return {"ativo": False, "url": url}


# ── episódios ─────────────────────────────────────────────────────────────────

def get_episodes_today() -> dict:
    today = _local_now().strftime("%Y-%m-%d")
    day_dir = PROJECT_DIR / "output" / today
    episodes = []

    if day_dir.is_dir():
        for folder in sorted(day_dir.iterdir()):
            if not folder.is_dir():
                continue
            meta: dict = {}
            meta_path = folder / "episode.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            has_audio = (folder / "episode.mp3").exists() or bool(meta.get("audio_path"))
            if not has_audio:
                continue
            parts = folder.name.split("_", 1)
            episodes.append({
                "pasta":      folder.name,
                "horario":    parts[0],
                "fonte":      parts[1] if len(parts) > 1 else folder.name,
                "nome":       meta.get("source_name", ""),
                "duracao_seg": meta.get("duration_seconds", 0),
            })

    total_seg = sum(e["duracao_seg"] for e in episodes)
    m, s = divmod(total_seg, 60)
    return {
        "data":          today,
        "total":         len(episodes),
        "duracao_total": f"{m}m {s}s" if total_seg else "—",
        "episodios":     episodes,
    }


# ── disco ─────────────────────────────────────────────────────────────────────

def get_disk_info() -> dict:
    output_dir = PROJECT_DIR / "output"
    output_mb = 0.0
    if output_dir.exists():
        total = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
        output_mb = round(total / 1024 / 1024, 1)

    try:
        usage = shutil.disk_usage(str(PROJECT_DIR))
        livre_gb = round(usage.free / 1024**3, 1)
    except Exception:
        livre_gb = 0.0

    return {"output_mb": output_mb, "disco_livre_gb": livre_gb}


# ── próximos agendamentos ─────────────────────────────────────────────────────

def get_next_scheduled(limit: int = 5) -> list:
    config = load_config()
    state_path = PROJECT_DIR / "scheduler_state.json"
    completed: set = set()
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            completed = set(state.get("completed_today", {}).keys())
        except Exception:
            pass

    today = _local_now().strftime("%Y-%m-%d")
    now_time = _local_now().strftime("%H:%M")

    proximos = []
    for entry in config.get("schedule", []):
        if entry.get("date"):
            continue
        t = str(entry.get("time", ""))
        if t < now_time:
            continue
        srcs = entry.get("sources", [])
        key_hint = f"{today}|{t}"
        if any(k.startswith(key_hint) for k in completed):
            continue
        proximos.append({
            "time":    t,
            "label":   entry.get("label", ""),
            "sources": srcs,
        })
        if len(proximos) >= limit:
            break

    return proximos


# ── snapshot completo ─────────────────────────────────────────────────────────

def get_system_snapshot() -> dict:
    config = load_config()
    radio_nome = config.get("radio", {}).get("name", "RadioIA")

    return {
        "radio":     {"nome": radio_nome},
        "scheduler": get_scheduler_status(),
        "player":    get_player_status(),
        "hoje":      get_episodes_today(),
        "disco":     get_disk_info(),
        "proximos":  get_next_scheduled(),
    }
