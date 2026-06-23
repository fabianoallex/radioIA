"""Provider edge-tts (padrão) — Microsoft Neural TTS via Edge browser, sem custo."""

import asyncio
import edge_tts

MAX_CHARS = 450   # limite conservador para evitar timeout no edge-tts


class EdgeTTSProvider:
    provider_name = 'edge_tts'
    model_name: str | None = None

    def __init__(self, config: dict):
        self._config = config or {}

    _CALL_TIMEOUT = 30  # segundos por chamada — evita hang silencioso da API

    async def synthesize(self, text: str, voice: str, output_path: str,
                         rate: str = '+0%', retries: int = 4) -> None:
        text = text[:MAX_CHARS]
        for attempt in range(retries):
            try:
                await asyncio.wait_for(
                    edge_tts.Communicate(text, voice, rate=rate).save(output_path),
                    timeout=self._CALL_TIMEOUT,
                )
                return
            except BaseException as e:
                if attempt < retries - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
                else:
                    # Última tentativa com texto reduzido
                    try:
                        await asyncio.wait_for(
                            edge_tts.Communicate(text[:200], voice, rate=rate).save(output_path),
                            timeout=self._CALL_TIMEOUT,
                        )
                        return
                    except BaseException:
                        raise RuntimeError(
                            f"EdgeTTS falhou após {retries} tentativas: {e}\nTexto: {text[:80]}"
                        )
