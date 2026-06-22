import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

OUTPUT_DIR   = Path(__file__).parent.parent.parent / "output"
HISTORY_PATH = Path(__file__).parent.parent.parent / "history.json"
GEN_STATUS   = Path(__file__).parent.parent.parent / "geracao_status.json"


def _clear_gen_status_if_matches(source_id: str, date: str) -> None:
    """Se geracao_status.json aponta para este episódio como 'concluido', neutraliza o etapa."""
    if not GEN_STATUS.exists():
        return
    try:
        st = json.loads(GEN_STATUS.read_text(encoding="utf-8"))
        if (not st.get("ativo")
                and st.get("etapa") == "concluido"
                and st.get("fonte") == source_id
                and st.get("data") == date):
            st["etapa"] = "cancelado"
            GEN_STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
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
    for folder in sorted(day_dir.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        audio = _resolve_audio(dt, folder.name)
        if not audio:
            continue
        meta: dict = {}
        ep_json = folder / "episode.json"
        if ep_json.exists():
            try:
                meta = json.loads(ep_json.read_text(encoding="utf-8"))
            except Exception:
                pass
        name = folder.name
        parts = name.split("_", 1)
        horario = parts[0].replace("-", ":") if len(parts) == 2 else ""
        source_id = parts[1] if len(parts) == 2 else name
        row: dict = {
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
        }
        if meta.get("replay_of"):
            row["replay_of"] = meta["replay_of"]
        result.append(row)
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


def _resolve_audio(dt: str, folder: str) -> Path | None:
    """Retorna o Path do MP3, seguindo audio_path em replays."""
    direct = OUTPUT_DIR / dt / folder / "episode.mp3"
    if direct.exists():
        return direct
    ep_json = OUTPUT_DIR / dt / folder / "episode.json"
    if ep_json.exists():
        try:
            meta = json.loads(ep_json.read_text(encoding="utf-8"))
            ap = meta.get("audio_path", "")
            if ap:
                p = Path(ap)
                if p.exists():
                    return p
        except Exception:
            pass
    return None


@router.get("/episodes/{dt}/{folder}/stream")
def stream_audio(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    audio = _resolve_audio(dt, folder)
    if not audio:
        raise HTTPException(404, "Áudio não encontrado")
    return FileResponse(str(audio), media_type="audio/mpeg")


def _load_pil_font(size: int):
    from PIL import ImageFont
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        w = draw.textbbox((0, 0), candidate, font=font)[2]
        if w <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _build_cover(radio_name: str, ep_name: str, horario: str, date: str,
                 duracao_seg: int, out: Path) -> None:
    from PIL import Image, ImageDraw

    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#18181b")
    draw = ImageDraw.Draw(img)

    font_title = _load_pil_font(64)
    font_name  = _load_pil_font(42)
    font_meta  = _load_pil_font(28)

    # Radio name — top center
    bbox = draw.textbbox((0, 0), radio_name, font=font_title)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, 130), radio_name,
              font=font_title, fill="#ffffff")

    # Separator
    draw.rectangle([(140, 240), (W - 140, 243)], fill="#3f3f46")

    # Episode name — center, wrapped
    lines = _wrap_text(draw, ep_name, font_name, W - 200)
    y = 290
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_name)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((W - lw) // 2, y), line, font=font_name, fill="#d4d4d8")
        y += lh + 14

    # Bottom metadata
    date_str = f"{date}  {horario}" if horario else date
    draw.text((100, H - 80), date_str, font=font_meta, fill="#71717a")

    if duracao_seg:
        m, s = divmod(duracao_seg, 60)
        h, m = divmod(m, 60)
        dur = f"{h}h {m:02d}min" if h else f"{m}min {s:02d}s"
        dur_w = draw.textbbox((0, 0), dur, font=font_meta)[2]
        draw.text((W - 100 - dur_w, H - 80), dur, font=font_meta, fill="#71717a")

    # Accent bar at bottom
    draw.rectangle([(0, H - 6), (W, H)], fill="#52525b")

    img.save(str(out))


@router.get("/episodes/{dt}/{folder}/download")
def download_audio(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    audio = _resolve_audio(dt, folder)
    if not audio:
        raise HTTPException(404, "Áudio não encontrado")
    return FileResponse(
        str(audio),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{folder}.mp3"'},
    )


@router.get("/episodes/{dt}/{folder}/download/mp4")
def download_mp4(dt: str, folder: str, background_tasks: BackgroundTasks):
    _chk_date(dt)
    _chk_folder(folder)

    from api.services.system_service import load_config
    cfg = load_config()
    dl = cfg.get("downloads", {})
    if not dl.get("enabled", True) or not dl.get("mp4", True):
        raise HTTPException(404, "Download MP4 não está habilitado")

    audio = _resolve_audio(dt, folder)
    if not audio:
        raise HTTPException(404, "Áudio não encontrado")

    ep_json = OUTPUT_DIR / dt / folder / "episode.json"
    meta: dict = {}
    if ep_json.exists():
        try:
            meta = json.loads(ep_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    radio_name = cfg.get("radio", {}).get("name", "RadioIA")
    ep_name    = meta.get("source_name") or folder.split("_", 1)[-1]
    parts      = folder.split("_", 1)
    horario    = parts[0].replace("-", ":") if len(parts) == 2 else ""
    duracao    = int(meta.get("duration_seconds") or 0)

    tmp = tempfile.mkdtemp()
    cover_path = Path(tmp) / "cover.png"
    mp4_path   = Path(tmp) / f"{folder}.mp4"

    try:
        _build_cover(radio_name, ep_name, horario, dt, duracao, cover_path)
    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(500, f"Erro ao gerar capa: {exc}")

    filt = (
        "[1:a]showwaves=s=1280x160:mode=cline:rate=25:colors=#a1a1aa[wv];"
        "[wv]colorkey=color=black:similarity=0.3:blend=0.05[wv_key];"
        "[0:v][wv_key]overlay=0:440:shortest=1[out]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(audio),
        "-filter_complex", filt,
        "-map", "[out]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        "-shortest",
        str(mp4_path),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(500, "Erro ao gerar MP4 via ffmpeg")

    background_tasks.add_task(shutil.rmtree, tmp, True)
    return FileResponse(
        str(mp4_path),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{folder}.mp4"'},
    )


@router.get("/episodes/{dt}/{folder}/prompt")
def get_prompt(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    f = OUTPUT_DIR / dt / folder / "prompt.txt"
    if not f.exists():
        raise HTTPException(404, "prompt.txt não encontrado")
    return PlainTextResponse(f.read_text(encoding="utf-8"))


@router.get("/episodes/{dt}/{folder}/script")
def get_script(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    f = OUTPUT_DIR / dt / folder / "script.txt"
    if not f.exists():
        raise HTTPException(404, "script.txt não encontrado")
    return PlainTextResponse(f.read_text(encoding="utf-8"))


@router.get("/episodes/{dt}/{folder}/log")
def get_log(dt: str, folder: str):
    _chk_date(dt)
    _chk_folder(folder)
    f = OUTPUT_DIR / dt / folder / "generation.log"
    if not f.exists():
        raise HTTPException(404, "generation.log não encontrado")
    return PlainTextResponse(f.read_text(encoding="utf-8"))


@router.post("/episodes/{dt}/{folder}/replay")
def replay_episode(dt: str, folder: str, target_dt: str | None = None):
    _chk_date(dt)
    _chk_folder(folder)

    orig_dir = OUTPUT_DIR / dt / folder
    orig_mp3 = orig_dir / "episode.mp3"
    orig_json = orig_dir / "episode.json"

    if not orig_dir.exists():
        raise HTTPException(404, "Episódio não encontrado")

    # Aceita replays mesmo quando o áudio está via audio_path (replay de replay)
    audio_path = _resolve_audio(dt, folder)
    if not audio_path:
        raise HTTPException(400, "Episódio sem áudio disponível para replay")

    if target_dt:
        _chk_date(target_dt)
    else:
        target_dt = datetime.now().strftime("%Y-%m-%d")

    now = datetime.now().strftime("%H-%M")
    source_id = folder.split("_", 1)[1] if "_" in folder else folder
    replay_folder = f"{now}_{source_id}"
    replay_dir = OUTPUT_DIR / target_dt / replay_folder

    replay_dir.mkdir(parents=True, exist_ok=True)

    meta: dict = {}
    if orig_json.exists():
        try:
            meta = json.loads(orig_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Remove campos de geração — o replay não é um novo episódio gerado
    meta.pop("generation", None)
    meta["audio_path"] = str(audio_path.resolve())
    meta["replay_of"] = f"{dt}/{folder}"
    meta["status"] = "published"

    (replay_dir / "episode.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {"replay": f"{target_dt}/{replay_folder}", "original": f"{dt}/{folder}"}


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

    source_id = folder.split("_", 1)[1] if "_" in folder else folder
    _clear_gen_status_if_matches(source_id, dt)

    shutil.rmtree(str(ep_dir), ignore_errors=True)
    return {"deleted": ep_id, "items_removed": items_removed}
