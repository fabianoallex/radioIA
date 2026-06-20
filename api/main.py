from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import system, sources, generate, episodes, schedule, spots, settings

app = FastAPI(title="RadioIA Admin", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(spots.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

_dist = Path(__file__).parent.parent / "ui" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="ui")
