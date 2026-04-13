from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.services.final_timeline_builder import build_final_preview_timeline
from app.services.render_repository import (
    finalize_render_job,
    get_render_job_by_id,
    list_successful_scene_tasks,
    mark_job_status,
)
from app.services.subtitle_burner import burn_subtitles, write_srt
from app.services.video_merger import merge_clips_concat


TERMINAL_JOB_STATUSES = {"completed", "failed"}
ACTIVE_POSTPROCESS_JOB_STATUSES = {"merging", "burning_subtitles"}


def _is_job_terminal(job) -> bool:
    return job.status in TERMINAL_JOB_STATUSES


def _is_job_already_in_postprocess(job) -> bool:
    return job.status in ACTIVE_POSTPROCESS_JOB_STATUSES


def _should_fail_due_to_partial_success(job) -> bool:
    return job.failed_scene_count > 0


async def process_render_postprocess(db: Session, job_id: str) -> None:
    job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not job:
        return

    if _is_job_terminal(job):
        return

    if _is_job_already_in_postprocess(job):
        return

    if _should_fail_due_to_partial_success(job):
        mark_job_status(
            db,
            job,
            "failed",
            "Postprocess blocked by partial success policy: all scenes must succeed before final merge.",
            source="postprocess",
            reason="partial_success_policy",
        )
        return

    successful_scenes = list_successful_scene_tasks(db, job_id)

    if not successful_scenes:
        mark_job_status(
            db,
            job,
            "failed",
            "No successful scenes available for postprocess.",
            source="postprocess",
            reason="no_successful_scenes",
        )
        return

    if len(successful_scenes) != job.planned_scene_count:
        mark_job_status(
            db,
            job,
            "failed",
            (
                "Postprocess blocked: successful scene count does not match planned_scene_count "
                f"({len(successful_scenes)}/{job.planned_scene_count})."
            ),
            source="postprocess",
            reason="successful_scene_count_mismatch",
        )
        return

    updated = mark_job_status(
        db,
        job,
        "merging",
        source="postprocess",
        reason="postprocess_started",
    )
    if not updated:
        return

    out_dir = Path("storage/render_outputs") / job.id
    out_dir.mkdir(parents=True, exist_ok=True)

    video_paths = [scene.local_video_path for scene in successful_scenes if scene.local_video_path]

    if len(video_paths) != len(successful_scenes):
        mark_job_status(
            db,
            job,
            "failed",
            "Postprocess blocked: one or more successful scenes are missing local_video_path.",
            source="postprocess",
            reason="missing_local_video_path",
        )
        return

    merged_path = str(out_dir / "merged.mp4")
    merge_clips_concat(video_paths, merged_path)

    final_path = merged_path

    if job.subtitle_mode == "burn":
        updated = mark_job_status(
            db,
            job,
            "burning_subtitles",
            source="postprocess",
            reason="subtitle_burn_started",
        )
        if not updated:
            return

        subtitle_segments: list[dict] = []
        srt_path = str(out_dir / "subtitles.srt")
        write_srt(subtitle_segments, srt_path)

        burned_path = str(out_dir / "merged_burned.mp4")
        burn_subtitles(merged_path, srt_path, burned_path)
        final_path = burned_path

    final_video_url = f"/storage/render_outputs/{job.id}/{Path(final_path).name}"

    final_timeline = build_final_preview_timeline(
        scenes=[
            {
                "scene_index": s.scene_index,
                "title": s.title,
                "video_url": s.output_video_url,
                "local_video_path": s.local_video_path,
            }
            for s in successful_scenes
        ],
        subtitle_segments=[],
        merged_video_url=final_video_url,
    )

    latest_job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not latest_job:
        return

    if _is_job_terminal(latest_job):
        return

    if _is_job_already_in_postprocess(latest_job) or latest_job.status == "polling":
        finalized = finalize_render_job(
            db,
            latest_job,
            final_video_url=final_video_url,
            final_video_path=final_path,
            final_timeline=final_timeline,
            source="postprocess",
        )
        if not finalized:
            return