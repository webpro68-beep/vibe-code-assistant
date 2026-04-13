from __future__ import annotations

import os
from pydantic import BaseModel


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings(BaseModel):
    voice_consent_min_chars: int = int(os.getenv("VOICE_CONSENT_MIN_CHARS", "20"))
    require_voice_consent: bool = _get_bool("REQUIRE_VOICE_CONSENT", True)
    default_music_gain_db: int = int(os.getenv("DEFAULT_MUSIC_GAIN_DB", "-18"))
    default_narration_gain_db: int = int(os.getenv("DEFAULT_NARRATION_GAIN_DB", "0"))
    default_music_ducking_db: int = int(os.getenv("DEFAULT_MUSIC_DUCKING_DB", "10"))
    default_breath_preset: str = os.getenv("DEFAULT_BREATH_PRESET", "natural")
    elevenlabs_enable_music: bool = _get_bool("ELEVENLABS_ENABLE_MUSIC", False)
    elevenlabs_default_similarity_boost: float = float(os.getenv("ELEVENLABS_DEFAULT_SIMILARITY_BOOST", "0.8"))
    elevenlabs_default_stability: float = float(os.getenv("ELEVENLABS_DEFAULT_STABILITY", "0.45"))
    elevenlabs_tts_output_format: str = os.getenv("ELEVENLABS_TTS_OUTPUT_FORMAT", "mp3_44100_128")
    elevenlabs_base_url: str = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")
    ffprobe_binary: str = os.getenv("FFPROBE_BINARY", "ffprobe")
    observability_enabled: bool = _get_bool("OBSERVABILITY_ENABLED", True)
    notification_plane_enabled: bool = _get_bool("NOTIFICATION_PLANE_ENABLED", True)
    decision_engine_enabled: bool = _get_bool("DECISION_ENGINE_ENABLED", True)
    decision_engine_policy_path: str | None = os.getenv("DECISION_ENGINE_POLICY_PATH")
    control_plane_enabled: bool = _get_bool("CONTROL_PLANE_ENABLED", True)
    default_dispatch_batch_limit: int = int(os.getenv("DEFAULT_DISPATCH_BATCH_LIMIT", "10"))
    default_poll_countdown_seconds: int = int(os.getenv("DEFAULT_POLL_COUNTDOWN_SECONDS", "60"))
    autopilot_control_fabric_enabled: bool = _get_bool("AUTOPILOT_CONTROL_FABRIC_ENABLED", True)

    audio_upload_dir: str = os.getenv("AUDIO_UPLOAD_DIR", "/app/storage/audio_uploads")
    audio_output_dir: str = os.getenv("AUDIO_OUTPUT_DIR", "/app/storage/audio_outputs")
    audio_output_format: str = os.getenv("AUDIO_OUTPUT_FORMAT", "mp3_44100_128")
    audio_upload_to_object_storage: bool = _get_bool("AUDIO_UPLOAD_TO_OBJECT_STORAGE", True)
    ffmpeg_binary: str = os.getenv("FFMPEG_BINARY", "ffmpeg")
    elevenlabs_api_key: str | None = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_tts_model_id: str = os.getenv("ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2")
    default_music_duration_seconds: int = _get_int("DEFAULT_MUSIC_DURATION_SECONDS", 30)
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/render_factory")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    storage_root: str = os.getenv("STORAGE_ROOT", "/app/storage")
    render_cache_dir: str = os.getenv("RENDER_CACHE_DIR", "/app/storage/render_cache")
    render_output_dir: str = os.getenv("RENDER_OUTPUT_DIR", "/app/storage/render_outputs")
    object_storage_provider: str = os.getenv("OBJECT_STORAGE_PROVIDER", "minio")
    s3_endpoint_url: str | None = os.getenv("S3_ENDPOINT_URL")
    s3_access_key_id: str | None = os.getenv("S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = os.getenv("S3_SECRET_ACCESS_KEY")
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "render-assets")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    s3_public_base_url: str | None = os.getenv("S3_PUBLIC_BASE_URL")
    signed_url_expires_seconds: int = _get_int("SIGNED_URL_EXPIRES_SECONDS", 3600)
    google_cloud_project: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    google_genai_use_vertex: bool = _get_bool("GOOGLE_GENAI_USE_VERTEX", True)
    google_application_credentials: str | None = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    veo_default_model: str = os.getenv("VEO_DEFAULT_MODEL", "veo-3.1-generate-001")
    veo_fast_model: str = os.getenv("VEO_FAST_MODEL", "veo-3.1-fast-generate-001")
    veo_output_gcs_uri: str | None = os.getenv("VEO_OUTPUT_GCS_URI")
    veo_batch_max_scripts: int = _get_int("VEO_BATCH_MAX_SCRIPTS", 100)
    veo_enable_sound_generation: bool = _get_bool("VEO_ENABLE_SOUND_GENERATION", False)
    veo_enable_reference_preview: bool = _get_bool("VEO_ENABLE_REFERENCE_PREVIEW", False)
    veo_reference_preview_model: str = os.getenv("VEO_REFERENCE_PREVIEW_MODEL", "veo-3.1-generate-preview")
    runway_api_secret: str | None = os.getenv("RUNWAYML_API_SECRET")
    runway_api_base_url: str = os.getenv("RUNWAY_API_BASE_URL", "https://api.dev.runwayml.com")
    runway_api_version: str = os.getenv("RUNWAY_API_VERSION", "2024-11-06")
    runway_default_model: str = os.getenv("RUNWAY_DEFAULT_MODEL", "gen4.5")
    kling_access_key: str | None = os.getenv("KLING_ACCESS_KEY")
    kling_secret_key: str | None = os.getenv("KLING_SECRET_KEY")
    kling_api_base_url: str = os.getenv("KLING_API_BASE_URL", "https://api.klingai.com")
    kling_default_model: str = os.getenv("KLING_DEFAULT_MODEL", "kling-v1")
    kling_token_ttl_seconds: int = _get_int("KLING_TOKEN_TTL_SECONDS", 1800)

    provider_callback_use_relay: bool = _get_bool("PROVIDER_CALLBACK_USE_RELAY", False)
    provider_callback_public_base_url: str | None = os.getenv("PROVIDER_CALLBACK_PUBLIC_BASE_URL")
    provider_callback_relay_path_template: str = os.getenv("PROVIDER_CALLBACK_RELAY_PATH_TEMPLATE", "/hooks/{provider}")
    provider_max_retries: int = _get_int("PROVIDER_MAX_RETRIES", 2)
    provider_retry_base_seconds: int = _get_int("PROVIDER_RETRY_BASE_SECONDS", 2)
    provider_allow_mock_fallback: bool = _get_bool("PROVIDER_ALLOW_MOCK_FALLBACK", True)
    provider_callback_shared_secret: str | None = os.getenv("PROVIDER_CALLBACK_SHARED_SECRET")
    provider_relay_shared_secret: str | None = os.getenv("PROVIDER_RELAY_SHARED_SECRET")
    runway_relay_shared_secret: str | None = os.getenv("RUNWAY_RELAY_SHARED_SECRET")
    kling_relay_shared_secret: str | None = os.getenv("KLING_RELAY_SHARED_SECRET")
    veo_relay_shared_secret: str | None = os.getenv("VEO_RELAY_SHARED_SECRET")
    provider_ingress_signature_ttl_seconds: int = _get_int("PROVIDER_INGRESS_SIGNATURE_TTL_SECONDS", 300)
    runway_callback_shared_secret: str | None = os.getenv("RUNWAY_CALLBACK_SHARED_SECRET")
    kling_callback_shared_secret: str | None = os.getenv("KLING_CALLBACK_SHARED_SECRET")
    kling_api_token: str | None = os.getenv("KLING_API_TOKEN")
    kling_text_to_video_path: str = os.getenv("KLING_TEXT_TO_VIDEO_PATH", "/v1/videos/text2video")
    kling_text_to_video_status_path_template: str = os.getenv("KLING_TEXT_TO_VIDEO_STATUS_PATH_TEMPLATE", "/v1/videos/text2video/{task_id}")
    provider_http_timeout_seconds: int = _get_int("PROVIDER_HTTP_TIMEOUT_SECONDS", 120)
    celery_task_time_limit: int = _get_int("CELERY_TASK_TIME_LIMIT", 1800)
    celery_task_soft_time_limit: int = _get_int("CELERY_TASK_SOFT_TIME_LIMIT", 1500)
    celery_worker_prefetch_multiplier: int = _get_int("CELERY_WORKER_PREFETCH_MULTIPLIER", 1)
    celery_task_acks_late: bool = _get_bool("CELERY_TASK_ACKS_LATE", True)


settings = Settings()
