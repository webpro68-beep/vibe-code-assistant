from __future__ import annotations

from typing import Any

from app.schemas.validation import ValidationIssue, ValidationResult


def validate_preview_with_issues(payload: dict[str, Any]) -> ValidationResult:
    issues: list[ValidationIssue] = []

    scenes = payload.get("scenes") or []
    subtitles = payload.get("subtitle_segments") or []
    script_text = (payload.get("script_text") or "").strip()

    if not script_text:
        issues.append(
            ValidationIssue(
                code="preview.script_text.empty",
                message="Script text is empty.",
                target_type="preview",
                field="script_text",
            )
        )

    if not scenes:
        issues.append(
            ValidationIssue(
                code="preview.scenes.empty",
                message="At least one scene is required.",
                target_type="preview",
                field="scenes",
            )
        )

    if not subtitles:
        issues.append(
            ValidationIssue(
                code="preview.subtitles.empty",
                message="At least one subtitle segment is required.",
                target_type="preview",
                field="subtitle_segments",
            )
        )

    expected_scene_index = 1
    valid_scene_indexes: set[int] = set()

    for i, scene in enumerate(scenes):
        row = i
        scene_index = int(scene.get("scene_index", 0))
        title = (scene.get("title") or "").strip()
        scene_text = (scene.get("script_text") or "").strip()
        duration = scene.get("target_duration_sec")

        if scene_index != expected_scene_index:
            issues.append(
                ValidationIssue(
                    code="scene.index.invalid",
                    message=f"Scene index must be {expected_scene_index}, got {scene_index}.",
                    target_type="scene",
                    target_index=row,
                    field="scene_index",
                )
            )
        else:
            valid_scene_indexes.add(scene_index)

        expected_scene_index += 1

        if not title:
            issues.append(
                ValidationIssue(
                    code="scene.title.empty",
                    message="Scene title cannot be empty.",
                    target_type="scene",
                    target_index=row,
                    field="title",
                )
            )

        if not scene_text:
            issues.append(
                ValidationIssue(
                    code="scene.script_text.empty",
                    message="Scene script text cannot be empty.",
                    target_type="scene",
                    target_index=row,
                    field="script_text",
                )
            )

        try:
            duration_value = float(duration)
            if duration_value <= 0:
                raise ValueError()
        except Exception:
            issues.append(
                ValidationIssue(
                    code="scene.duration.invalid",
                    message="Scene duration must be greater than 0.",
                    target_type="scene",
                    target_index=row,
                    field="target_duration_sec",
                )
            )

    prev_end = -1.0

    for i, subtitle in enumerate(subtitles):
        row = i
        text = (subtitle.get("text") or "").strip()
        scene_index = subtitle.get("scene_index")
        start_sec = subtitle.get("start_sec")
        end_sec = subtitle.get("end_sec")

        if not text:
            issues.append(
                ValidationIssue(
                    code="subtitle.text.empty",
                    message="Subtitle text cannot be empty.",
                    target_type="subtitle",
                    target_index=row,
                    field="text",
                )
            )

        try:
            start_value = float(start_sec)
            if start_value < 0:
                raise ValueError()
        except Exception:
            issues.append(
                ValidationIssue(
                    code="subtitle.start.invalid",
                    message="Subtitle start time must be 0 or greater.",
                    target_type="subtitle",
                    target_index=row,
                    field="start_sec",
                )
            )
            start_value = None

        try:
            end_value = float(end_sec)
            if end_value <= 0:
                raise ValueError()
        except Exception:
            issues.append(
                ValidationIssue(
                    code="subtitle.end.invalid",
                    message="Subtitle end time must be greater than 0.",
                    target_type="subtitle",
                    target_index=row,
                    field="end_sec",
                )
            )
            end_value = None

        if start_value is not None and end_value is not None and end_value <= start_value:
            issues.append(
                ValidationIssue(
                    code="subtitle.range.invalid",
                    message="Subtitle end time must be greater than start time.",
                    target_type="subtitle",
                    target_index=row,
                    field="end_sec",
                )
            )

        if (
            start_value is not None
            and end_value is not None
            and start_value < prev_end
        ):
            issues.append(
                ValidationIssue(
                    code="subtitle.timeline.overlap",
                    message="Subtitle overlaps or is out of order.",
                    target_type="subtitle",
                    target_index=row,
                    field="start_sec",
                )
            )

        if end_value is not None and start_value is not None and end_value > start_value:
            prev_end = end_value

        if scene_index is not None:
            try:
                scene_index_value = int(scene_index)
                if scene_index_value not in valid_scene_indexes:
                    issues.append(
                        ValidationIssue(
                            code="subtitle.scene_index.invalid",
                            message=f"Subtitle references missing scene_index {scene_index_value}.",
                            target_type="subtitle",
                            target_index=row,
                            field="scene_index",
                        )
                    )
            except Exception:
                issues.append(
                    ValidationIssue(
                        code="subtitle.scene_index.invalid_type",
                        message="Subtitle scene_index must be a valid integer or empty.",
                        target_type="subtitle",
                        target_index=row,
                        field="scene_index",
                    )
                )

    return ValidationResult(
        valid=len([issue for issue in issues if issue.severity == "error"]) == 0,
        issues=issues,
    )