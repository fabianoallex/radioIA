from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services import system_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "RadioIA Admin API"}


@router.get("/system")
def get_system():
    return system_service.get_system_snapshot()


class SchedulerAction(BaseModel):
    action: str  # "start" | "stop"


@router.post("/system/scheduler")
def control_scheduler(body: SchedulerAction):
    if body.action == "start":
        return system_service.start_scheduler()
    if body.action == "stop":
        return system_service.stop_scheduler()
    raise HTTPException(status_code=400, detail=f"Ação inválida: '{body.action}'. Use 'start' ou 'stop'.")
