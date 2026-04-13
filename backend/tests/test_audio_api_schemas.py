from app.schemas.audio import NarrationJobCreateRequest, MusicAssetCreateRequest


def test_audio_schema_defaults():
    narration = NarrationJobCreateRequest(voice_profile_id="vp1", script_text="Hello there")
    assert narration.style_preset == "natural_conversational"
    music = MusicAssetCreateRequest(display_name="Calm Bed")
    assert music.source_mode == "library"
    assert music.force_instrumental is True
