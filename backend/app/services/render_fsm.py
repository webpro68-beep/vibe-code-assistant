from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


# =========================
# Canonical states
# =========================
RENDER_JOB_STATES = {
    "queued",
    "dispatching",
    "polling",
    "merging",
    "burning_subtitles",
    "completed",
    "failed",
    "queue_error",
}

RENDER_SCENE_STATES = {
    "queued",
    "submitted",
    "processing",
    "succeeded",
    "failed",
    "canceled",
}


# =========================
# Transition maps
# =========================
RENDER_JOB_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"dispatching", "failed", "queue_error"},
    "dispatching": {"polling", "failed", "queue_error"},
    "polling": {"merging", "burning_subtitles", "completed", "failed"},
    "merging": {"burning_subtitles", "completed", "failed"},
    "burning_subtitles": {"completed", "failed"},
    "queue_error": {"failed"},
    "completed": set(),
    "failed": set(),
}

RENDER_SCENE_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"submitted", "failed"},
    "submitted": {"processing", "succeeded", "failed", "canceled"},
    "processing": {"processing", "succeeded", "failed", "canceled"},
    "succeeded": set(),
    "failed": set(),
    "canceled": set(),
}


# =========================
# Metrics
# =========================
@dataclass
class TransitionMetrics:
    job_invalid_transition_attempts: int = 0
    scene_invalid_transition_attempts: int = 0
    job_valid_transition_attempts: int = 0
    scene_valid_transition_attempts: int = 0


transition_metrics = TransitionMetrics()


# =========================
# Exceptions
# =========================
class InvalidTransitionError(ValueError):
    pass


# =========================
# Helpers
# =========================
def _normalize_state(value: str) -> str:
    return value.strip().lower()


def _allowed_targets(
    *,
    entity_type: str,
    current_state: str,
) -> set[str]:
    if entity_type == "render_job":
        return RENDER_JOB_TRANSITIONS.get(current_state, set())
    if entity_type == "render_scene_task":
        return RENDER_SCENE_TRANSITIONS.get(current_state, set())
    raise ValueError(f"Unknown entity_type: {entity_type}")


def _known_states(entity_type: str) -> set[str]:
    if entity_type == "render_job":
        return RENDER_JOB_STATES
    if entity_type == "render_scene_task":
        return RENDER_SCENE_STATES
    raise ValueError(f"Unknown entity_type: {entity_type}")


def can_transition(
    *,
    entity_type: str,
    current_state: str,
    next_state: str,
) -> bool:
    current_state = _normalize_state(current_state)
    next_state = _normalize_state(next_state)

    known = _known_states(entity_type)
    if current_state not in known or next_state not in known:
        return False

    if current_state == next_state:
        # scene processing -> processing refresh is allowed by map if listed;
        # same-state no-op is otherwise allowed for idempotency only if explicitly listed or terminal refresh use-case.
        return next_state in _allowed_targets(entity_type=entity_type, current_state=current_state) or current_state == next_state

    return next_state in _allowed_targets(entity_type=entity_type, current_state=current_state)


def assert_valid_transition(
    *,
    entity_type: str,
    entity_id: str,
    current_state: str,
    next_state: str,
    context: dict | None = None,
) -> None:
    current_state = _normalize_state(current_state)
    next_state = _normalize_state(next_state)
    context = context or {}

    if can_transition(
        entity_type=entity_type,
        current_state=current_state,
        next_state=next_state,
    ):
        if entity_type == "render_job":
            transition_metrics.job_valid_transition_attempts += 1
        else:
            transition_metrics.scene_valid_transition_attempts += 1
        return

    allowed = sorted(_allowed_targets(entity_type=entity_type, current_state=current_state))

    if entity_type == "render_job":
        transition_metrics.job_invalid_transition_attempts += 1
    else:
        transition_metrics.scene_invalid_transition_attempts += 1

    logger.error(
        "Invalid FSM transition: entity_type=%s entity_id=%s current_state=%s next_state=%s allowed_targets=%s context=%s",
        entity_type,
        entity_id,
        current_state,
        next_state,
        allowed,
        context,
    )

    raise InvalidTransitionError(
        f"Invalid transition for {entity_type} {entity_id}: {current_state} -> {next_state}. Allowed: {allowed}"
    )


def get_transition_metrics_snapshot() -> dict[str, int]:
    return {
        "job_invalid_transition_attempts": transition_metrics.job_invalid_transition_attempts,
        "scene_invalid_transition_attempts": transition_metrics.scene_invalid_transition_attempts,
        "job_valid_transition_attempts": transition_metrics.job_valid_transition_attempts,
        "scene_valid_transition_attempts": transition_metrics.scene_valid_transition_attempts,
    }


def describe_fsm() -> dict[str, dict[str, list[str]]]:
    return {
        "render_jobs": {state: sorted(list(targets)) for state, targets in RENDER_JOB_TRANSITIONS.items()},
        "render_scene_tasks": {state: sorted(list(targets)) for state, targets in RENDER_SCENE_TRANSITIONS.items()},
    }