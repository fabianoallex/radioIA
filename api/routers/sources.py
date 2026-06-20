from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services import config_service, plugin_registry

router = APIRouter(tags=["sources"])


def _enrich(src: dict, type_map: dict) -> dict:
    info = type_map.get(src.get("type", ""), {})
    return {
        **src,
        "plugin_info": {
            "name":         info.get("name", src.get("type", "")),
            "icon":         info.get("icon", "package"),
            "description":  info.get("description", ""),
            "has_metadata": info.get("has_metadata", False),
            "config_schema": info.get("config_schema", []),
        },
    }


@router.get("/sources")
def list_sources():
    sources = config_service.get_sources()
    type_map = plugin_registry.get_type_map()
    return [_enrich(s, type_map) for s in sources]


@router.post("/sources/{source_id}/toggle")
def toggle_source(source_id: str):
    try:
        return config_service.toggle_source(source_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class UpdateSourceBody(BaseModel):
    fields: dict


@router.put("/sources/{source_id}")
def update_source(source_id: str, body: UpdateSourceBody):
    try:
        return config_service.update_source(source_id, body.fields)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class AddSourceBody(BaseModel):
    source: dict


@router.post("/sources")
def add_source(body: AddSourceBody):
    try:
        type_map = plugin_registry.get_type_map()
        return _enrich(config_service.add_source(body.source), type_map)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    try:
        config_service.remove_source(source_id)
        return {"status": "ok", "id": source_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/plugins")
def list_plugins():
    configured_types = {s.get("type") for s in config_service.get_sources()}
    plugins = plugin_registry.get_plugin_types()
    for p in plugins:
        p["configured"] = p["type"] in configured_types
    return plugins
