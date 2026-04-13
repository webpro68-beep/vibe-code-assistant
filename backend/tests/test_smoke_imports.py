from app.services.script_ingestion import (
    build_subtitle_segments_from_scenes,
    normalize_script_text,
    split_script_into_scenes,
)


def test_script_ingestion_flow():
    text = normalize_script_text("Hello world.\n\nThis is scene two.")
    scenes = split_script_into_scenes(text, max_scenes=4)
    subtitles = build_subtitle_segments_from_scenes(scenes)
    assert len(scenes) >= 1
    assert len(subtitles) >= 1
