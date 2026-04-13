from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceProfileCreateRequest(BaseModel):
    display_name: str
    clone_mode: str = "library"
    language_code: str | None = "en"
    provider_voice_id: str | None = None
    owner_user_id: str | None = None
    consent_text: str
    consent_confirmed: bool = True


class VoiceProfileResponse(BaseModel):
    id: str
    display_name: str
    provider: str
    provider_voice_id: str | None = None
    clone_mode: str
    consent_status: str
    owner_user_id: str | None = None
    language_code: str | None = None
    is_active: bool


class VoiceSampleUploadResponse(BaseModel):
    id: str
    voice_profile_id: str
    filename: str
    public_url: str | None = None
    storage_key: str | None = None


class NarrationJobCreateRequest(BaseModel):
    voice_profile_id: str
    render_job_id: str | None = None
    script_text: str
    style_preset: str = "natural_conversational"
    breath_pacing_preset: str = "cinematic_slow"
    provider: str = "elevenlabs"


class NarrationSegmentResponse(BaseModel):
    id: str
    narration_job_id: str
    segment_index: int
    text: str
    pause_after_ms: int
    estimated_duration_ms: int | None = None
    output_url: str | None = None


class NarrationJobResponse(BaseModel):
    id: str
    render_job_id: str | None = None
    voice_profile_id: str
    status: str
    style_preset: str
    breath_pacing_preset: str
    output_url: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    segments: list[NarrationSegmentResponse] = []


class MusicAssetCreateRequest(BaseModel):
    display_name: str
    source_mode: str = "library"
    provider: str | None = None
    prompt_text: str | None = None
    mood: str | None = None
    bpm: int | None = Field(default=None, ge=40, le=220)
    force_instrumental: bool = True
    license_note: str | None = None


class MusicAssetResponse(BaseModel):
    id: str
    display_name: str
    source_mode: str
    provider: str | None = None
    prompt_text: str | None = None
    mood: str | None = None
    bpm: int | None = None
    public_url: str | None = None


class AudioMixJobCreateRequest(BaseModel):
    render_job_id: str | None = None
    narration_job_id: str
    music_asset_id: str | None = None
    mix_profile_id: str | None = None
    mux_to_video: bool = False


class AudioRenderOutputResponse(BaseModel):
    id: str
    render_job_id: str | None = None
    narration_job_id: str | None = None
    music_asset_id: str | None = None
    mix_profile_id: str | None = None
    status: str
    voice_track_url: str | None = None
    music_track_url: str | None = None
    mixed_audio_url: str | None = None
    final_muxed_video_url: str | None = None
    error_message: str | None = None


class AudioPreviewRequest(BaseModel):
    voice_profile_id: str
    text: str
    style_preset: str = "natural_conversational"
