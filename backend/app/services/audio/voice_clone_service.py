from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.voice_profile import VoiceProfile
from app.models.voice_sample import VoiceSample
from app.services.audio.elevenlabs_adapter import ElevenLabsAdapter
from app.services.object_storage import upload_file_to_object_storage


def create_voice_profile(
    db: Session,
    *,
    display_name: str,
    clone_mode: str,
    language_code: str | None,
    provider_voice_id: str | None,
    owner_user_id: str | None,
    consent_text: str,
    consent_confirmed: bool,
) -> VoiceProfile:
    profile = VoiceProfile(
        display_name=display_name,
        provider="elevenlabs",
        provider_voice_id=provider_voice_id,
        clone_mode=clone_mode,
        consent_status="confirmed" if consent_confirmed else "pending",
        consent_text=consent_text,
        owner_user_id=owner_user_id,
        language_code=language_code,
        is_active=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def save_voice_sample(
    db: Session,
    *,
    voice_profile_id: str,
    source_path: str,
    filename: str,
    uploaded_by: str | None,
    mime_type: str | None,
    remove_background_noise: bool = False,
) -> VoiceSample:
    target_dir = Path(settings.audio_upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    shutil.copyfile(source_path, target_path)

    raw_bytes = target_path.read_bytes()
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    storage_key = f"audio/voice-samples/{voice_profile_id}/{filename}"
    stored = None
    if settings.audio_upload_to_object_storage:
        try:
            stored = upload_file_to_object_storage(local_path=str(target_path), key=storage_key, content_type=mime_type)
        except Exception:
            stored = None

    sample = VoiceSample(
        voice_profile_id=voice_profile_id,
        filename=filename,
        local_path=str(target_path),
        storage_key=stored.key if stored else storage_key,
        public_url=stored.public_url if stored else None,
        mime_type=mime_type,
        sha256_hex=sha256_hex,
        uploaded_by=uploaded_by,
        remove_background_noise=remove_background_noise,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


async def clone_voice_if_needed(db: Session, profile: VoiceProfile) -> VoiceProfile:
    if profile.provider_voice_id or profile.clone_mode == "library":
        return profile

    sample_paths = [
        row.local_path
        for row in db.query(VoiceSample).filter(VoiceSample.voice_profile_id == profile.id).all()
    ]
    if not sample_paths:
        return profile

    adapter = ElevenLabsAdapter()
    result = await adapter.create_ivc_voice(name=profile.display_name, files=sample_paths, remove_background_noise=True)
    if result.get("ok"):
        profile.provider_voice_id = result["body"].get("voice_id")
        profile.consent_status = "confirmed"
        db.commit()
        db.refresh(profile)
    return profile
