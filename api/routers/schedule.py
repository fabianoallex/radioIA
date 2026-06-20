from fastapi import APIRouter
from pydantic import BaseModel

from api.services.config_service import load_config, save_config

router = APIRouter(tags=["schedule"])


class ScheduleBody(BaseModel):
    slots: list[dict]


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
