from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audio_render_output import AudioRenderOutput
from app.models.render_job import RenderJob
from app.services.object_storage import upload_file_to_object_storage


def mux_audio_to_video(db: Session, audio_output_id: str) -> AudioRenderOutput:
    output = db.query(AudioRenderOutput).filter(AudioRenderOutput.id == audio_output_id).first()
    if output is None:
        raise ValueError(f"Audio output not found: {audio_output_id}")
    if not output.render_job_id:
        output.status = "failed"
        output.error_message = "render_job_id is required for mux"
        db.commit()
        return output

    job = db.query(RenderJob).filter(RenderJob.id == output.render_job_id).first()
    if job is None:
        output.status = "failed"
        output.error_message = "Render job not found"
        db.commit()
        return output

    video_path = job.final_video_path or job.output_path
    audio_path = output.local_mixed_audio_path
    if not video_path or not audio_path:
        output.status = "failed"
        output.error_message = "Video or mixed audio path is missing"
        db.commit()
        return output

    target_dir = Path(settings.audio_output_dir) / "mux" / output.id
    target_dir.mkdir(parents=True, exist_ok=True)
    muxed_path = target_dir / "final_muxed_video.mp4"

    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(muxed_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        output.status = "failed"
        output.error_message = completed.stderr[-4000:]
        db.commit()
        return output

    output.local_muxed_video_path = str(muxed_path)
    key = f"video/final-mux/{output.id}/final_muxed_video.mp4"
    try:
        stored = upload_file_to_object_storage(local_path=str(muxed_path), key=key, content_type="video/mp4")
        output.final_muxed_video_url = stored.public_url
    except Exception:
        output.final_muxed_video_url = None

    output.status = "completed"
    db.commit()
    db.refresh(output)
    return output
