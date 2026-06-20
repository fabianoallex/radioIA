"""Leitura e escrita do config.yaml para a Admin API."""
from pathlib import Path
import yaml

PROJECT_DIR = Path(__file__).parent.parent.parent
_CONFIG_PATH = PROJECT_DIR / "config.yaml"


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict) -> None:
    for entry in config.get("schedule", []):
        t = entry.get("time")
        if isinstance(t, int):
            entry["time"] = f"{t // 60:02d}:{t % 60:02d}"
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, indent=2)


def get_sources() -> list[dict]:
    return load_config().get("sources", [])


def toggle_source(source_id: str) -> dict:
    config = load_config()
    sources = config.get("sources", [])
    idx = next((i for i, s in enumerate(sources) if s["id"] == source_id), None)
    if idx is None:
        raise ValueError(f"Fonte '{source_id}' não encontrada")
    prev = sources[idx].get("enabled", True)
    sources[idx]["enabled"] = not prev
    config["sources"] = sources
    save_config(config)
    return {"id": source_id, "enabled": not prev}


def update_source(source_id: str, fields: dict) -> dict:
    config = load_config()
    sources = config.get("sources", [])
    idx = next((i for i, s in enumerate(sources) if s["id"] == source_id), None)
    if idx is None:
        raise ValueError(f"Fonte '{source_id}' não encontrada")
    sources[idx].update(fields)
    config["sources"] = sources
    save_config(config)
    return sources[idx]


def add_source(source: dict) -> dict:
    config = load_config()
    sources = config.get("sources", [])
    if any(s["id"] == source["id"] for s in sources):
        raise ValueError(f"Fonte '{source['id']}' já existe")
    sources.append(source)
    config["sources"] = sources
    save_config(config)
    return source


def remove_source(source_id: str) -> None:
    config = load_config()
    sources = config.get("sources", [])
    before = len(sources)
    config["sources"] = [s for s in sources if s["id"] != source_id]
    if len(config["sources"]) == before:
        raise ValueError(f"Fonte '{source_id}' não encontrada")
    save_config(config)
