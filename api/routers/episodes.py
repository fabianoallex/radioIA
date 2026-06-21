import io
import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
HISTORY_PATH = Path(__file__).parent.parent.parent / "history.json"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

router = APIRouter(tags=["episodes"])


def _chk_date(dt: str):
    if not DATE_RE.match(dt):
        raise HTTPException(400, "Data inválida")


def _chk_folder(folder: str):
    if ".." in folder or "/" in folder or "\\" in folder:
        raise HTTPException(400, "Pasta inválida")


def _scan(dt: str) -> list[dict]:
    day_dir = OUTPUT_DIR / dt
    if not day_dir.exists():
        return []
    result = []
    for folder in sorted(day_dir.iterdir()):
        if not folder.is_dir():
            continue
        audio = folder / "episode.mp3"
        if not audio.exists():
            continue
        meta: dict = {}
        ep_json = folder / "episode.json"
        if ep_json.exists():
            try:
                meta = json.loads(ep_json.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Folder format: HH-MM_source_id
        name = folder.name
        parts = name.split("_", 1)
        horario = parts[0].replace("-", ":") if len(parts) == 2 else ""
        source_id = parts[1] if len(parts) == 2 else name
        result.append({
            "pasta":         name,
            "horario":       horario,
            "source_id":     source_id,
            "nome":          meta.get("source_name") or source_id,
            "duracao_seg":   int(meta.get("duration_seconds") or 0),
            "tamanho_bytes": audio.stat().st_size,
            "date":          dt,
            "status":        meta.get("status", "published"),
            "links":         meta.get("links", []),
            "generation":    meta.get("generation"),
        })
    return result


# ── routes: literals BEFORE path params ──────────────────────────

@router.get("/episodes/dates")
def list_dates():
    if not OUTPUT_DIR.exists():
        return {"dates": []}
    dates = sorted(
        [d.name for d in OUTPUT_DIR.iterdir()
         if d.is_dir() and DATE_RE.match(d.name)],
        reverse=True,
    )
    return {"dates": dates}


@router.get("/episodes/today")
def episodes_today():
    dt = datetime.now().strftime("%Y-%m-%d")
    return {"date": dt, "episodios": _scan(dt)}


@router.get("/episodes")
def list_episodes(date: str | None = None):
    if date:
        _chk_date(date)
        return {"date": date, "episodios": _scan(date)}
    return {"date": None, "episodios": []}


@router.get("/episodes/{dt}/export/zip")
def export_zip(dt: str):
    _chk_date(dt)
    day_dir = OUTPUT_DIR / dt
    if not day_dir.exists():
        raise HTTPException(404, "Data não encontrada")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for audio in sorted(day_dir.rglob("episode.mp3")):
            zf.write(str(audio), f"{audio.parent.name}/{audio.name}")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="radio_{dt}.zip"'},
    )


@router.get("/episodes/{dt}/{folder}/stream")
def stream_audio(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    audio = OUTPUT_DIR / dt / folder / "episode.mp3"
    if not audio.exists():
        raise HTTPException(404, "Áudio não encontrado")
    return FileResponse(str(audio), media_type="audio/mpeg")


@router.get("/episodes/{dt}/{folder}/download")
def download_audio(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    audio = OUTPUT_DIR / dt / folder / "episode.mp3"
    if not audio.exists():
        raise HTTPException(404, "Áudio não encontrado")
    return FileResponse(
        str(audio),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{folder}.mp3"'},
    )


class StatusBody(BaseModel):
    status: str  # "published" ou "draft"


@router.patch("/episodes/{dt}/{folder}/status")
def patch_status(dt: str, folder: str, body: StatusBody):
    _chk_date(dt)
    _chk_folder(folder)
    if body.status not in ("published", "draft"):
        raise HTTPException(400, "status inválido — use published ou draft")
    ep_json = OUTPUT_DIR / dt / folder / "episode.json"
    if not ep_json.exists():
        raise HTTPException(404, "episode.json não encontrado")
    meta = json.loads(ep_json.read_text(encoding="utf-8"))
    meta["status"] = body.status
    ep_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": body.status}


@router.delete("/episodes/{dt}/{folder}")
def delete_episode(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    ep_dir = OUTPUT_DIR / dt / folder
    if not ep_dir.exists():
        raise HTTPException(404, "Episódio não encontrado")

    items_removed = 0
    ep_id = f"{dt}/{folder}"
    if HISTORY_PATH.exists():
        try:
            hist = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            ep_entry = next(
                (e for e in hist.get("episodes", []) if e.get("episode_id") == ep_id), None
            )
            if ep_entry:
                id_set = {v["id"] for v in ep_entry.get("videos", [])}
                hist["seen_ids"] = [i for i in hist.get("seen_ids", []) if i not in id_set]
                hist["episodes"] = [e for e in hist.get("episodes", []) if e.get("episode_id") != ep_id]
                items_removed = len(id_set)
                HISTORY_PATH.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    shutil.rmtree(str(ep_dir), ignore_errors=True)
    return {"deleted": ep_id, "items_removed": items_removed}
