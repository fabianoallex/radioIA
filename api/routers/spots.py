from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.config_service import load_config, save_config

router = APIRouter(tags=["spots"])


def _get_spots(config: dict) -> list:
    s = config.get("spots")
    return s if isinstance(s, list) else []


class SpotBody(BaseModel):
    id: str
    type: str                           # file | tts | llm
    weight: int = 1
    path: str | None = None             # file
    text: str | None = None             # tts
    topic: str | None = None            # llm
    duration_seconds: int | None = None # llm
    model: str | None = None            # llm
    voice: str | None = None
    rate: str | None = None


class SpotConfigBody(BaseModel):
    fallback_every: int | None = None
    between_episodes_every: int | None = None


def _body_to_dict(b: SpotBody) -> dict:
    d: dict = {"id": b.id, "type": b.type, "weight": b.weight}
    if b.type == "file" and b.path:
        d["path"] = b.path
    if b.type == "tts" and b.text:
        d["text"] = b.text
    if b.type == "llm":
        if b.topic:
            d["topic"] = b.topic
        if b.duration_seconds is not None:
            d["duration_seconds"] = b.duration_seconds
        if b.model:
            d["model"] = b.model
    if b.voice:
        d["voice"] = b.voice
    if b.rate:
        d["rate"] = b.rate
    return d


@router.get("/spots")
def get_spots():
    config = load_config()
    return {
        "spots": _get_spots(config),
        "spots_config": config.get("spots_config", {}),
    }


@router.post("/spots")
def create_spot(body: SpotBody):
    config = load_config()
    spots = _get_spots(config)
    if any(s["id"] == body.id for s in spots):
        raise HTTPException(400, f"Spot '{body.id}' já existe")
    spots.append(_body_to_dict(body))
    config["spots"] = spots
    save_config(config)
    return {"spot": _body_to_dict(body)}


@router.put("/spots/{spot_id}")
def update_spot(spot_id: str, body: SpotBody):
    config = load_config()
    spots = _get_spots(config)
    idx = next((i for i, s in enumerate(spots) if s["id"] == spot_id), None)
    if idx is None:
        raise HTTPException(404, f"Spot '{spot_id}' não encontrado")
    spots[idx] = _body_to_dict(body)
    config["spots"] = spots
    save_config(config)
    return {"spot": spots[idx]}


@router.delete("/spots/{spot_id}")
def delete_spot(spot_id: str):
    config = load_config()
    spots = _get_spots(config)
    before = len(spots)
    spots = [s for s in spots if s["id"] != spot_id]
    if len(spots) == before:
        raise HTTPException(404, f"Spot '{spot_id}' não encontrado")
    config["spots"] = spots if spots else None
    save_config(config)
    return {"deleted": spot_id}


@router.put("/spots-config")
def update_spots_config(body: SpotConfigBody):
    config = load_config()
    sc = config.get("spots_config", {})
    if body.fallback_every is not None:
        sc["fallback_every"] = body.fallback_every
    if body.between_episodes_every is not None:
        sc["between_episodes_every"] = body.between_episodes_every
    config["spots_config"] = sc
    save_config(config)
    return {"spots_config": sc}
