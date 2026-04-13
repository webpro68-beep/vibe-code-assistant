from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.music_asset import MusicAsset
from app.services.audio.elevenlabs_adapter import ElevenLabsAdapter
from app.services.object_storage import upload_file_to_object_storage


def create_music_asset(
    db: Session,
    *,
    display_name: str,
    source_mode: str,
    provider: str | None,
    prompt_text: str | None,
    mood: str | None,
    bpm: int | None,
    force_instrumental: bool,
    license_note: str | None,
) -> MusicAsset:
    asset = MusicAsset(
        display_name=display_name,
        source_mode=source_mode,
        provider=provider,
        prompt_text=prompt_text,
        mood=mood,
        bpm=bpm,
        force_instrumental=force_instrumental,
        license_note=license_note,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def save_uploaded_music_asset(
    db: Session,
    *,
    asset_id: str,
    source_path: str,
    filename: str,
    content_type: str | None,
) -> MusicAsset:
    asset = db.query(MusicAsset).filter(MusicAsset.id == asset_id).first()
    if asset is None:
        raise ValueError(f"Music asset not found: {asset_id}")

    target_dir = Path(settings.audio_output_dir) / "music" / asset.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    shutil.copyfile(source_path, target_path)

    asset.local_path = str(target_path)
    storage_key = f"audio/music/{asset.id}/{filename}"
    try:
        stored = upload_file_to_object_storage(local_path=str(target_path), key=storage_key, content_type=content_type or "audio/mpeg")
        asset.storage_key = stored.key
        asset.public_url = stored.public_url
    except Exception:
        asset.storage_key = storage_key
    db.commit()
    db.refresh(asset)
    return asset


async def generate_music_asset(db: Session, asset_id: str) -> MusicAsset:
    asset = db.query(MusicAsset).filter(MusicAsset.id == asset_id).first()
    if asset is None:
        raise ValueError(f"Music asset not found: {asset_id}")
    if asset.source_mode != "generate":
        return asset

    adapter = ElevenLabsAdapter()
    audio_bytes = await adapter.compose_music(
        prompt_text=asset.prompt_text,
        duration_seconds=settings.default_music_duration_seconds,
        force_instrumental=asset.force_instrumental,
    )
    target_dir = Path(settings.audio_output_dir) / "music" / asset.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "generated_music.mp3"
    target_path.write_bytes(audio_bytes)
    asset.local_path = str(target_path)
    storage_key = f"audio/music/{asset.id}/generated_music.mp3"
    try:
        stored = upload_file_to_object_storage(local_path=str(target_path), key=storage_key, content_type="audio/mpeg")
        asset.storage_key = stored.key
        asset.public_url = stored.public_url
    except Exception:
        asset.storage_key = storage_key
    db.commit()
    db.refresh(asset)
    return asset
