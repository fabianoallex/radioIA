from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.config_service import load_config, save_config

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings():
    config = load_config()
    return {
        "radio":         config.get("radio", {}),
        "narrators":     config.get("narrators", []),
        "llm":           config.get("llm", {}),
        "vinheta":       config.get("vinheta", {}),
        "announcements": config.get("announcements", {}),
        "downloads":     config.get("downloads", {}),
        "welcome_intro": config.get("welcome_intro", {}),
    }


# ── Radio ──────────────────────────────────────────────────────────────────────

class RadioBody(BaseModel):
    name: str
    background_music: str = ""
    background_volume_db: int = -22


@router.put("/settings/radio")
def update_radio(body: RadioBody):
    config = load_config()
    config["radio"] = body.model_dump()
    save_config(config)
    return {"radio": config["radio"]}


# ── Narrators ──────────────────────────────────────────────────────────────────

class Narrator(BaseModel):
    name: str
    voice: str
    personality: str = ""


class NarratorsBody(BaseModel):
    narrators: list[Narrator]


@router.put("/settings/narrators")
def update_narrators(body: NarratorsBody):
    config = load_config()
    config["narrators"] = [n.model_dump() for n in body.narrators]
    save_config(config)
    return {"narrators": config["narrators"]}


# ── LLM ────────────────────────────────────────────────────────────────────────

class LlmBody(BaseModel):
    model: str


@router.put("/settings/llm")
def update_llm(body: LlmBody):
    config = load_config()
    llm = config.get("llm", {})
    llm["model"] = body.model
    config["llm"] = llm
    save_config(config)
    return {"llm": config["llm"]}


# ── Vinheta ────────────────────────────────────────────────────────────────────

class VinhetaBody(BaseModel):
    voice: str
    rate: str = "+20%"


@router.put("/settings/vinheta")
def update_vinheta(body: VinhetaBody):
    config = load_config()
    config["vinheta"] = body.model_dump()
    save_config(config)
    return {"vinheta": config["vinheta"]}


# ── Downloads ──────────────────────────────────────────────────────────────────

class DownloadsBody(BaseModel):
    enabled: bool = True
    individual: bool = True
    concatenated: bool = True
    zip: bool = True


@router.put("/settings/downloads")
def update_downloads(body: DownloadsBody):
    config = load_config()
    config["downloads"] = body.model_dump()
    save_config(config)
    return {"downloads": config["downloads"]}


# ── Announcements ──────────────────────────────────────────────────────────────

class AnnouncementsBody(BaseModel):
    enabled: bool = True


@router.put("/settings/announcements")
def update_announcements(body: AnnouncementsBody):
    config = load_config()
    config["announcements"] = body.model_dump()
    save_config(config)
    return {"announcements": config["announcements"]}


# ── Welcome intro ──────────────────────────────────────────────────────────────

class WelcomeBody(BaseModel):
    falas: list[str]


@router.put("/settings/welcome")
def update_welcome(body: WelcomeBody):
    config = load_config()
    config["welcome_intro"] = {"falas": [f for f in body.falas if f.strip()]}
    save_config(config)
    return {"welcome_intro": config["welcome_intro"]}
