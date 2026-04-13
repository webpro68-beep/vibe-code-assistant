from app.services.audio.breath_pacing_service import build_breath_paced_segments


def test_build_breath_paced_segments_splits_and_pauses():
    segments = build_breath_paced_segments("Hello world. This is a longer sentence, with a pause!", "cinematic_slow")
    assert len(segments) == 2
    assert segments[0]["pause_after_ms"] > 0
    assert segments[1]["estimated_duration_ms"] > 0
