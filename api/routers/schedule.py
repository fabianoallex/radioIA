import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from api.services.config_service import load_config, save_config

router = APIRouter(tags=["schedule"])

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_STATE_FILE = Path(__file__).parent.parent.parent / "scheduler_state.json"


class ScheduleBody(BaseModel):
    slots: list[dict]


@router.get("/schedule/replay-status")
def get_replay_status():
    today = datetime.now().strftime("%Y-%m-%d")
    pmap_today: dict = {}
    try:
        state = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        pmap_today = state.get("programacao_map", {}).get(today, {})
    except Exception:
        pass

    config = load_config()
    missing: list[int] = []
    for slot in config.get("schedule", []):
        replay_of = slot.get("replay_of")
        if replay_of is None:
            continue
        ep_id = pmap_today.get(str(replay_of))
        if not ep_id:
            missing.append(int(replay_of))
            continue
        if not (_OUTPUT_DIR / ep_id / "episode.mp3").exists():
            missing.append(int(replay_of))

    return {"date": today, "missing": missing}


@router.get("/schedule")
def get_schedule():
    config = load_config()
    return {"slots": config.get("schedule", [])}


@router.put("/schedule")
def update_schedule(body: ScheduleBody):
    config = load_config()
    # Sort by time before saving
    sorted_slots = sorted(body.slots, key=lambda s: str(s.get("time", "")))
    config["schedule"] = sorted_slots
    save_config(config)
    return {"slots": config["schedule"]}
