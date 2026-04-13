from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audio_render_output import AudioRenderOutput
from app.models.music_asset import MusicAsset
from app.models.narration_job import NarrationJob
from app.models.narration_segment import NarrationSegment
from app.models.voice_profile import VoiceProfile
from app.schemas.audio import (
    AudioMixJobCreateRequest,
    AudioRenderOutputResponse,
    AudioPreviewRequest,
    MusicAssetCreateRequest,
    MusicAssetResponse,
    NarrationJobCreateRequest,
    NarrationJobResponse,
    NarrationSegmentResponse,
    VoiceProfileCreateRequest,
    VoiceProfileResponse,
    VoiceSampleUploadResponse,
)
from app.services.audio.audio_mix_service import create_audio_render_output, mix_audio_tracks
from app.services.audio.audio_mux_service import mux_audio_to_video
from app.services.audio.elevenlabs_adapter import ElevenLabsAdapter
from app.services.audio.music_selection_service import create_music_asset, generate_music_asset, save_uploaded_music_asset
from app.services.audio.narration_service import create_narration_job, run_narration_job
from app.services.audio.voice_clone_service import create_voice_profile, save_voice_sample

router = APIRouter(prefix="/api/v1/audio", tags=["audio-studio"])


def _voice_profile_to_response(row: VoiceProfile) -> VoiceProfileResponse:
    return VoiceProfileResponse(
        id=row.id,
        display_name=row.display_name,
        provider=row.provider,
        provider_voice_id=row.provider_voice_id,
        clone_mode=row.clone_mode,
        consent_status=row.consent_status,
        owner_user_id=row.owner_user_id,
        language_code=row.language_code,
        is_active=row.is_active,
    )


def _narration_job_to_response(db: Session, row: NarrationJob) -> NarrationJobResponse:
    segments = db.query(NarrationSegment).filter(NarrationSegment.narration_job_id == row.id).order_by(NarrationSegment.segment_index.asc()).all()
    return NarrationJobResponse(
        id=row.id,
        render_job_id=row.render_job_id,
        voice_profile_id=row.voice_profile_id,
        status=row.status,
        style_preset=row.style_preset,
        breath_pacing_preset=row.breath_pacing_preset,
        output_url=row.output_url,
        duration_ms=row.duration_ms,
        error_message=row.error_message,
        segments=[
            NarrationSegmentResponse(
                id=s.id,
                narration_job_id=s.narration_job_id,
                segment_index=s.segment_index,
                text=s.text,
                pause_after_ms=s.pause_after_ms,
                estimated_duration_ms=s.estimated_duration_ms,
                output_url=s.output_url,
            )
            for s in segments
        ],
    )


@router.get("/voice-profiles", response_model=list[VoiceProfileResponse])
async def list_voice_profiles(db: Session = Depends(get_db)):
    rows = db.query(VoiceProfile).order_by(VoiceProfile.created_at.desc()).all()
    return [_voice_profile_to_response(row) for row in rows]


@router.post("/voice-profiles", response_model=VoiceProfileResponse)
async def post_voice_profile(payload: VoiceProfileCreateRequest, db: Session = Depends(get_db)):
    if not payload.consent_confirmed:
        raise HTTPException(status_code=400, detail="consent_confirmed must be true")
    row = create_voice_profile(
        db,
        display_name=payload.display_name,
        clone_mode=payload.clone_mode,
        language_code=payload.language_code,
        provider_voice_id=payload.provider_voice_id,
        owner_user_id=payload.owner_user_id,
        consent_text=payload.consent_text,
        consent_confirmed=payload.consent_confirmed,
    )
    return _voice_profile_to_response(row)


@router.post("/voice-profiles/{voice_profile_id}/samples", response_model=VoiceSampleUploadResponse)
async def post_voice_sample(
    voice_profile_id: str,
    file: UploadFile = File(...),
    uploaded_by: str | None = None,
    remove_background_noise: bool = True,
    db: Session = Depends(get_db),
):
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / file.filename
        temp_path.write_bytes(await file.read())
        row = save_voice_sample(
            db,
            voice_profile_id=voice_profile_id,
            source_path=str(temp_path),
            filename=file.filename,
            uploaded_by=uploaded_by,
            mime_type=file.content_type,
            remove_background_noise=remove_background_noise,
        )
    return VoiceSampleUploadResponse(
        id=row.id,
        voice_profile_id=row.voice_profile_id,
        filename=row.filename,
        public_url=row.public_url,
        storage_key=row.storage_key,
    )


@router.post("/preview")
async def post_audio_preview(payload: AudioPreviewRequest, db: Session = Depends(get_db)):
    profile = db.query(VoiceProfile).filter(VoiceProfile.id == payload.voice_profile_id).first()
    if profile is None or not profile.provider_voice_id:
        raise HTTPException(status_code=404, detail="Voice profile with provider_voice_id not found")
    adapter = ElevenLabsAdapter()
    audio_bytes = await adapter.synthesize_speech(voice_id=profile.provider_voice_id, text=payload.text)
    return {"ok": True, "bytes_length": len(audio_bytes)}


@router.post("/narration-jobs", response_model=NarrationJobResponse)
async def post_narration_job(payload: NarrationJobCreateRequest, db: Session = Depends(get_db)):
    row = create_narration_job(
        db,
        voice_profile_id=payload.voice_profile_id,
        render_job_id=payload.render_job_id,
        script_text=payload.script_text,
        style_preset=payload.style_preset,
        breath_pacing_preset=payload.breath_pacing_preset,
        provider=payload.provider,
    )
    row = await run_narration_job(db, row.id)
    return _narration_job_to_response(db, row)


@router.get("/narration-jobs/{narration_job_id}", response_model=NarrationJobResponse)
async def get_narration_job(narration_job_id: str, db: Session = Depends(get_db)):
    row = db.query(NarrationJob).filter(NarrationJob.id == narration_job_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Narration job not found")
    return _narration_job_to_response(db, row)


@router.get("/music-assets", response_model=list[MusicAssetResponse])
async def list_music_assets(db: Session = Depends(get_db)):
    rows = db.query(MusicAsset).order_by(MusicAsset.created_at.desc()).all()
    return [
        MusicAssetResponse(
            id=row.id,
            display_name=row.display_name,
            source_mode=row.source_mode,
            provider=row.provider,
            prompt_text=row.prompt_text,
            mood=row.mood,
            bpm=row.bpm,
            public_url=row.public_url,
        ) for row in rows
    ]


@router.post("/music-assets", response_model=MusicAssetResponse)
async def post_music_asset(payload: MusicAssetCreateRequest, db: Session = Depends(get_db)):
    row = create_music_asset(
        db,
        display_name=payload.display_name,
        source_mode=payload.source_mode,
        provider=payload.provider,
        prompt_text=payload.prompt_text,
        mood=payload.mood,
        bpm=payload.bpm,
        force_instrumental=payload.force_instrumental,
        license_note=payload.license_note,
    )
    if row.source_mode == "generate":
        row = await generate_music_asset(db, row.id)
    return MusicAssetResponse(
        id=row.id,
        display_name=row.display_name,
        source_mode=row.source_mode,
        provider=row.provider,
        prompt_text=row.prompt_text,
        mood=row.mood,
        bpm=row.bpm,
        public_url=row.public_url,
    )


@router.post("/music-assets/{music_asset_id}/upload", response_model=MusicAssetResponse)
async def post_music_asset_upload(
    music_asset_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / file.filename
        temp_path.write_bytes(await file.read())
        row = save_uploaded_music_asset(
            db,
            asset_id=music_asset_id,
            source_path=str(temp_path),
            filename=file.filename,
            content_type=file.content_type,
        )
    return MusicAssetResponse(
        id=row.id,
        display_name=row.display_name,
        source_mode=row.source_mode,
        provider=row.provider,
        prompt_text=row.prompt_text,
        mood=row.mood,
        bpm=row.bpm,
        public_url=row.public_url,
    )


@router.post("/mix-jobs", response_model=AudioRenderOutputResponse)
async def post_mix_job(payload: AudioMixJobCreateRequest, db: Session = Depends(get_db)):
    row = create_audio_render_output(
        db,
        render_job_id=payload.render_job_id,
        narration_job_id=payload.narration_job_id,
        music_asset_id=payload.music_asset_id,
        mix_profile_id=payload.mix_profile_id,
    )
    row = mix_audio_tracks(db, row.id)
    if payload.mux_to_video and row.status == "completed":
        row = mux_audio_to_video(db, row.id)
    return AudioRenderOutputResponse(
        id=row.id,
        render_job_id=row.render_job_id,
        narration_job_id=row.narration_job_id,
        music_asset_id=row.music_asset_id,
        mix_profile_id=row.mix_profile_id,
        status=row.status,
        voice_track_url=row.voice_track_url,
        music_track_url=row.music_track_url,
        mixed_audio_url=row.mixed_audio_url,
        final_muxed_video_url=row.final_muxed_video_url,
        error_message=row.error_message,
    )


@router.get("/mix-jobs/{audio_output_id}", response_model=AudioRenderOutputResponse)
async def get_mix_job(audio_output_id: str, db: Session = Depends(get_db)):
    row = db.query(AudioRenderOutput).filter(AudioRenderOutput.id == audio_output_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Audio render output not found")
    return AudioRenderOutputResponse(
        id=row.id,
        render_job_id=row.render_job_id,
        narration_job_id=row.narration_job_id,
        music_asset_id=row.music_asset_id,
        mix_profile_id=row.mix_profile_id,
        status=row.status,
        voice_track_url=row.voice_track_url,
        music_track_url=row.music_track_url,
        mixed_audio_url=row.mixed_audio_url,
        final_muxed_video_url=row.final_muxed_video_url,
        error_message=row.error_message,
    )
