from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.narration_job import NarrationJob
from app.models.narration_segment import NarrationSegment
from app.models.voice_profile import VoiceProfile
from app.services.audio.breath_pacing_service import build_breath_paced_segments
from app.services.audio.elevenlabs_adapter import ElevenLabsAdapter
from app.services.audio.voice_clone_service import clone_voice_if_needed
from app.services.object_storage import upload_file_to_object_storage


def create_narration_job(
    db: Session,
    *,
    voice_profile_id: str,
    render_job_id: str | None,
    script_text: str,
    style_preset: str,
    breath_pacing_preset: str,
    provider: str,
) -> NarrationJob:
    job = NarrationJob(
        voice_profile_id=voice_profile_id,
        render_job_id=render_job_id,
        script_text=script_text,
        style_preset=style_preset,
        breath_pacing_preset=breath_pacing_preset,
        provider=provider,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    segments = build_breath_paced_segments(script_text, breath_pacing_preset)
    for segment in segments:
        db.add(
            NarrationSegment(
                narration_job_id=job.id,
                segment_index=segment["segment_index"],
                text=segment["text"],
                pause_after_ms=segment["pause_after_ms"],
                estimated_duration_ms=segment["estimated_duration_ms"],
            )
        )
    db.commit()
    db.refresh(job)
    return job


async def run_narration_job(db: Session, narration_job_id: str) -> NarrationJob:
    job = db.query(NarrationJob).filter(NarrationJob.id == narration_job_id).first()
    if job is None:
        raise ValueError(f"Narration job not found: {narration_job_id}")

    profile = db.query(VoiceProfile).filter(VoiceProfile.id == job.voice_profile_id).first()
    if profile is None:
        job.status = "failed"
        job.error_message = "Voice profile not found"
        db.commit()
        return job

    profile = await clone_voice_if_needed(db, profile)
    if not profile.provider_voice_id:
        job.status = "failed"
        job.error_message = "provider_voice_id is missing after clone attempt"
        db.commit()
        return job

    adapter = ElevenLabsAdapter()
    segments = (
        db.query(NarrationSegment)
        .filter(NarrationSegment.narration_job_id == job.id)
        .order_by(NarrationSegment.segment_index.asc())
        .all()
    )

    output_dir = Path(settings.audio_output_dir) / "narration" / job.id
    output_dir.mkdir(parents=True, exist_ok=True)

    combined_audio = b""
    total_duration = 0
    job.status = "processing"
    db.commit()

    for segment in segments:
        audio_bytes = await adapter.synthesize_speech(
            voice_id=profile.provider_voice_id,
            text=segment.text,
            model_id=settings.elevenlabs_tts_model_id,
            output_format=settings.audio_output_format,
        )
        segment_path = output_dir / f"segment_{segment.segment_index:03d}.mp3"
        segment_path.write_bytes(audio_bytes)
        segment.output_local_path = str(segment_path)

        storage_key = f"audio/narration/{job.id}/{segment_path.name}"
        try:
            stored = upload_file_to_object_storage(local_path=str(segment_path), key=storage_key, content_type="audio/mpeg")
            segment.output_storage_key = stored.key
            segment.output_url = stored.public_url
        except Exception:
            segment.output_storage_key = storage_key
            segment.output_url = None

        combined_audio += audio_bytes
        total_duration += int(segment.estimated_duration_ms or 0)

    final_path = output_dir / "narration_combined.mp3"
    final_path.write_bytes(combined_audio)
    final_key = f"audio/narration/{job.id}/narration_combined.mp3"
    try:
        stored = upload_file_to_object_storage(local_path=str(final_path), key=final_key, content_type="audio/mpeg")
        job.output_storage_key = stored.key
        job.output_url = stored.public_url
    except Exception:
        job.output_storage_key = final_key
        job.output_url = None

    job.output_local_path = str(final_path)
    job.duration_ms = total_duration
    job.status = "completed"
    db.commit()
    db.refresh(job)
    return job
