from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings


class ElevenLabsAdapter:
    base_url = "https://api.elevenlabs.io"

    def __init__(self) -> None:
        self.api_key = settings.elevenlabs_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "xi-api-key": self.api_key or "",
        }

    async def list_voices(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/shared-voices",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return {"ok": False, "status_code": resp.status_code, "body": resp.text}
            return {"ok": True, "body": resp.json()}

    async def create_ivc_voice(
        self,
        *,
        name: str,
        files: list[str],
        remove_background_noise: bool = True,
    ) -> dict[str, Any]:
        multipart = []
        for file_path in files:
            p = Path(file_path)
            multipart.append(("files", (p.name, p.read_bytes(), "audio/mpeg")))
        multipart.append(("name", (None, name)))
        multipart.append(("remove_background_noise", (None, "true" if remove_background_noise else "false")))

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/voices/add",
                headers=self._headers(),
                files=multipart,
            )
            if resp.status_code >= 400:
                return {"ok": False, "status_code": resp.status_code, "body": resp.text}
            return {"ok": True, "body": resp.json()}

    async def synthesize_speech(
        self,
        *,
        voice_id: str,
        text: str,
        model_id: str | None = None,
        output_format: str = "mp3_44100_128",
    ) -> bytes:
        payload = {
            "text": text,
            "model_id": model_id or settings.elevenlabs_tts_model_id,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/text-to-speech/{voice_id}",
                headers={**self._headers(), "Content-Type": "application/json"},
                params={"output_format": output_format},
                json=payload,
            )
            resp.raise_for_status()
            return resp.content

    async def compose_music(
        self,
        *,
        prompt_text: str | None = None,
        duration_seconds: int = 30,
        force_instrumental: bool = True,
    ) -> bytes:
        payload = {
            "prompt": prompt_text,
            "duration_seconds": duration_seconds,
            "force_instrumental": force_instrumental,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/music",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.content
