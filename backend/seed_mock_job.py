from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.db.session import SessionLocal
from app.models.render_job import RenderJob
from app.models.render_scene_task import RenderSceneTask


def utcnow():
    return datetime.now(timezone.utc)


def main() -> None:
    db = SessionLocal()
    try:
        job = RenderJob(
            project_id="proj_seed_001",
            provider="mock",
            aspect_ratio="16:9",
            style_preset="cinematic_dark",
            subtitle_mode="soft",
            status="queued",
            planned_scene_count=2,
            created_at=utcnow(),
            updated_at=utcnow(),
            subtitle_segments=[
                {"start_sec": 0.0, "end_sec": 1.8, "text": "Opening line"},
                {"start_sec": 1.8, "end_sec": 4.0, "text": "A second subtitle"},
                {"start_sec": 4.0, "end_sec": 6.5, "text": "Scene two starts"},
            ],
        )
        db.add(job)
        db.flush()

        base = Path("storage/mock_assets")

        scene1 = RenderSceneTask(
            job_id=job.id,
            scene_index=1,
            title="Intro",
            script_text="Opening scene",
            provider_target_duration_sec=4,
            target_duration_sec=4,
            status="queued",
            output_path=str(base / "scene_0001.mp4"),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        scene2 = RenderSceneTask(
            job_id=job.id,
            scene_index=2,
            title="Second",
            script_text="Second scene",
            provider_target_duration_sec=5,
            target_duration_sec=5,
            status="queued",
            output_path=str(base / "scene_0002.mp4"),
            created_at=utcnow(),
            updated_at=utcnow(),
        )

        db.add(scene1)
        db.add(scene2)
        db.commit()

        print(f"Seeded mock render job: {job.id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()