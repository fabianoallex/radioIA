import asyncio
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

PROJECT_DIR = Path(__file__).parent.parent.parent

router = APIRouter(tags=["generate"])


class GenerateBody(BaseModel):
    sources: list[str]       # ["youtube", "noticias|foco em tech", "musica:3"]


@router.post("/generate")
async def generate(body: GenerateBody):
    if not body.sources:
        async def empty():
            yield "data: [ERRO:nenhuma fonte selecionada]\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    cmd = [sys.executable, str(PROJECT_DIR / "main.py")] + body.sources

    async def event_stream():
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(PROJECT_DIR),
            )

            async for raw in process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    safe = line.replace("\n", " ").replace("\r", "")
                    yield f"data: {safe}\n\n"

            await process.wait()
            if process.returncode == 0:
                yield "data: [CONCLUIDO]\n\n"
            else:
                yield f"data: [ERRO:exit {process.returncode}]\n\n"

        except Exception as e:
            yield f"data: [ERRO:{e}]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
