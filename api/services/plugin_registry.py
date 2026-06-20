"""Descobre plugins disponíveis e extrai seus metadados."""
import importlib.util
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent
PLUGINS_DIR = PROJECT_DIR / "plugins"

# Metadados dos tipos built-in (não vivem em plugins/)
BUILTIN_METADATA: dict[str, dict] = {
    "youtube": {
        "name": "YouTube",
        "description": "Vídeos de canais do YouTube com transcrição automática",
        "icon": "youtube",
        "credentials": ["YOUTUBE_API_KEY"],
        "config_schema": [],
    },
    "rss": {
        "name": "RSS",
        "description": "Feeds RSS/Atom com scraping de artigos",
        "icon": "rss",
        "credentials": [],
        "config_schema": [],
    },
    "utility": {
        "name": "Utilidades",
        "description": "Clima, câmbio, loterias, futebol via APIs públicas",
        "icon": "bar-chart-2",
        "credentials": [],
        "config_schema": [],
    },
    "music": {
        "name": "Música",
        "description": "Bloco musical — biblioteca local ou Jamendo",
        "icon": "music",
        "credentials": [],
        "config_schema": [],
    },
    "combined": {
        "name": "Combinado",
        "description": "Agrega múltiplas fontes em um único episódio",
        "icon": "layers",
        "credentials": [],
        "config_schema": [],
    },
    "clipping_auto": {
        "name": "Clipping Auto",
        "description": "Clipping automático com descoberta de tópicos por LLM",
        "icon": "trending-up",
        "credentials": [],
        "config_schema": [],
    },
}

# Ícones padrão por nome de plugin (fallback quando não há METADATA)
_DEFAULT_ICONS: dict[str, str] = {
    "reddit":    "message-square",
    "horoscopo": "star",
    "efemerides": "book-open",
    "receitas":  "utensils",
    "filmes":    "film",
    "biblia":    "book",
    "trivia":    "help-circle",
    "url":       "link",
    "clipping":  "newspaper",
    "podcast":   "mic",
    "whatsapp":  "message-circle",
    "concursos_pci": "award",
}


def _safe_load_metadata(plugin_name: str) -> dict | None:
    """Importa o plugin e extrai METADATA, capturando erros de import."""
    py_path = PLUGINS_DIR / f"{plugin_name}.py"
    if not py_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(f"_plugin_{plugin_name}", py_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return getattr(module, "METADATA", None)
    except Exception:
        return None


def _make_display_name(plugin_name: str) -> str:
    return plugin_name.replace("_", " ").title()


def get_plugin_types() -> list[dict]:
    """Retorna todos os tipos de plugin/fonte disponíveis."""
    result: list[dict] = []

    # Plugins da pasta plugins/
    for py_file in sorted(PLUGINS_DIR.glob("*.py")):
        name = py_file.stem
        if name.startswith("_") or name == "exemplo_plugin":
            continue

        meta = _safe_load_metadata(name)
        entry: dict = {
            "type":         name,
            "name":         meta.get("name", _make_display_name(name)) if meta else _make_display_name(name),
            "description":  meta.get("description", "") if meta else "",
            "icon":         meta.get("icon", _DEFAULT_ICONS.get(name, "package")) if meta else _DEFAULT_ICONS.get(name, "package"),
            "credentials":  meta.get("credentials", []) if meta else [],
            "config_schema": meta.get("config_schema", []) if meta else [],
            "has_metadata": meta is not None,
            "source":       "plugin",
        }
        result.append(entry)

    # Tipos built-in
    for type_id, meta in BUILTIN_METADATA.items():
        result.append({
            "type":         type_id,
            "name":         meta["name"],
            "description":  meta["description"],
            "icon":         meta["icon"],
            "credentials":  meta.get("credentials", []),
            "config_schema": meta.get("config_schema", []),
            "has_metadata": True,
            "source":       "builtin",
        })

    return result


def get_type_map() -> dict[str, dict]:
    return {p["type"]: p for p in get_plugin_types()}
