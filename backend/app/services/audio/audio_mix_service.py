from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audio_mix_profile import AudioMixProfile
from app.models.audio_render_output import AudioRenderOutput
from app.models.music_asset import MusicAsset
from app.models.narration_job import NarrationJob
from app.services.object_storage import upload_file_to_object_storage


def ensure_default_mix_profile(db: Session) -> AudioMixProfile:
    row = db.query(AudioMixProfile).order_by(AudioMixProfile.created_at.asc()).first()
    if row:
        return row
    row = AudioMixProfile(display_name="Default cinematic mix")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_audio_render_output(
    db: Session,
    *,
    render_job_id: str | None,
    narration_job_id: str,
    music_asset_id: str | None,
    mix_profile_id: str | None,
) -> AudioRenderOutput:
    profile = db.query(AudioMixProfile).filter(AudioMixProfile.id == mix_profile_id).first() if mix_profile_id else ensure_default_mix_profile(db)
    output = AudioRenderOutput(
        render_job_id=render_job_id,
        narration_job_id=narration_job_id,
        music_asset_id=music_asset_id,
        mix_profile_id=profile.id if profile else None,
        status="queued",
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


def mix_audio_tracks(db: Session, audio_output_id: str) -> AudioRenderOutput:
    output = db.query(AudioRenderOutput).filter(AudioRenderOutput.id == audio_output_id).first()
    if output is None:
        raise ValueError(f"Audio output not found: {audio_output_id}")

    narration = db.query(NarrationJob).filter(NarrationJob.id == output.narration_job_id).first()
    music = db.query(MusicAsset).filter(MusicAsset.id == output.music_asset_id).first() if output.music_asset_id else None
    profile = db.query(AudioMixProfile).filter(AudioMixProfile.id == output.mix_profile_id).first()

    if narration is None or not narration.output_local_path:
        output.status = "failed"
        output.error_message = "Narration audio is missing"
        db.commit()
        return output

    voice_path = Path(narration.output_local_path)
    output.voice_track_url = narration.output_url
    output.status = "processing"
    db.commit()

    target_dir = Path(settings.audio_output_dir) / "mix" / output.id
    target_dir.mkdir(parents=True, exist_ok=True)
    mixed_path = target_dir / "mixed_audio.mp3"

    if music and music.local_path:
        output.music_track_url = music.public_url
        cmd = [
            settings.ffmpeg_binary,
            "-y",
            "-i", str(voice_path),
            "-i", str(music.local_path),
            "-filter_complex",
            "amix=inputs=2:duration=longest:dropout_transition=2",
            "-c:a", "mp3",
            str(mixed_path),
        ]
    else:
        cmd = [
            settings.ffmpeg_binary,
            "-y",
            "-i", str(voice_path),
            "-c:a", "copy",
            str(mixed_path),
        ]

    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        output.status = "failed"
        output.error_message = completed.stderr[-4000:]
        db.commit()
        return output

    output.local_mixed_audio_path = str(mixed_path)
    key = f"audio/mix/{output.id}/mixed_audio.mp3"
    try:
        stored = upload_file_to_object_storage(local_path=str(mixed_path), key=key, content_type="audio/mpeg")
        output.mixed_audio_url = stored.public_url
    except Exception:
        output.mixed_audio_url = None

    output.status = "completed"
    db.commit()
    db.refresh(output)
    return output
