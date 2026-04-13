"""add audio studio tables

Revision ID: 20260411_0017
Revises: 20260411_0016
Create Date: 2026-04-11 00:17:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0017"
down_revision = "20260411_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_voice_id", sa.String(length=255), nullable=True),
        sa.Column("clone_mode", sa.String(length=64), nullable=False),
        sa.Column("consent_status", sa.String(length=32), nullable=False),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voice_profiles")),
    )
    op.create_index(op.f("ix_voice_profiles_display_name"), "voice_profiles", ["display_name"], unique=False)
    op.create_index(op.f("ix_voice_profiles_provider_voice_id"), "voice_profiles", ["provider_voice_id"], unique=False)
    op.create_index(op.f("ix_voice_profiles_owner_user_id"), "voice_profiles", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_voice_profiles_consent_status"), "voice_profiles", ["consent_status"], unique=False)
    op.create_index(op.f("ix_voice_profiles_is_active"), "voice_profiles", ["is_active"], unique=False)

    op.create_table(
        "voice_samples",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("voice_profile_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("sha256_hex", sa.String(length=128), nullable=True),
        sa.Column("uploaded_by", sa.String(length=255), nullable=True),
        sa.Column("remove_background_noise", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["voice_profile_id"], ["voice_profiles.id"], name=op.f("fk_voice_samples_voice_profile_id_voice_profiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voice_samples")),
    )
    op.create_index(op.f("ix_voice_samples_voice_profile_id"), "voice_samples", ["voice_profile_id"], unique=False)

    op.create_table(
        "narration_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("render_job_id", sa.String(length=36), nullable=True),
        sa.Column("voice_profile_id", sa.String(length=36), nullable=False),
        sa.Column("script_text", sa.Text(), nullable=False),
        sa.Column("style_preset", sa.String(length=64), nullable=False),
        sa.Column("breath_pacing_preset", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_job_id", sa.String(length=255), nullable=True),
        sa.Column("output_local_path", sa.Text(), nullable=True),
        sa.Column("output_storage_key", sa.Text(), nullable=True),
        sa.Column("output_url", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["render_job_id"], ["render_jobs.id"], name=op.f("fk_narration_jobs_render_job_id_render_jobs")),
        sa.ForeignKeyConstraint(["voice_profile_id"], ["voice_profiles.id"], name=op.f("fk_narration_jobs_voice_profile_id_voice_profiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_narration_jobs")),
    )
    op.create_index(op.f("ix_narration_jobs_render_job_id"), "narration_jobs", ["render_job_id"], unique=False)
    op.create_index(op.f("ix_narration_jobs_voice_profile_id"), "narration_jobs", ["voice_profile_id"], unique=False)
    op.create_index(op.f("ix_narration_jobs_status"), "narration_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_narration_jobs_provider_job_id"), "narration_jobs", ["provider_job_id"], unique=False)

    op.create_table(
        "narration_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("narration_job_id", sa.String(length=36), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("pause_after_ms", sa.Integer(), nullable=False),
        sa.Column("estimated_duration_ms", sa.Integer(), nullable=True),
        sa.Column("output_local_path", sa.Text(), nullable=True),
        sa.Column("output_storage_key", sa.Text(), nullable=True),
        sa.Column("output_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["narration_job_id"], ["narration_jobs.id"], name=op.f("fk_narration_segments_narration_job_id_narration_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_narration_segments")),
    )
    op.create_index(op.f("ix_narration_segments_narration_job_id"), "narration_segments", ["narration_job_id"], unique=False)

    op.create_table(
        "music_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("source_mode", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_asset_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("mood", sa.String(length=64), nullable=True),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("force_instrumental", sa.Boolean(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_music_assets")),
    )
    op.create_index(op.f("ix_music_assets_display_name"), "music_assets", ["display_name"], unique=False)
    op.create_index(op.f("ix_music_assets_mood"), "music_assets", ["mood"], unique=False)

    op.create_table(
        "audio_mix_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("voice_gain_db", sa.Float(), nullable=False),
        sa.Column("music_gain_db", sa.Float(), nullable=False),
        sa.Column("ducking_strength", sa.Float(), nullable=False),
        sa.Column("normalize_lufs", sa.Float(), nullable=False),
        sa.Column("fade_in_ms", sa.Integer(), nullable=False),
        sa.Column("fade_out_ms", sa.Integer(), nullable=False),
        sa.Column("enable_ducking", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_mix_profiles")),
    )
    op.create_index(op.f("ix_audio_mix_profiles_display_name"), "audio_mix_profiles", ["display_name"], unique=False)

    op.create_table(
        "audio_render_outputs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("render_job_id", sa.String(length=36), nullable=True),
        sa.Column("narration_job_id", sa.String(length=36), nullable=True),
        sa.Column("music_asset_id", sa.String(length=36), nullable=True),
        sa.Column("mix_profile_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("voice_track_url", sa.Text(), nullable=True),
        sa.Column("music_track_url", sa.Text(), nullable=True),
        sa.Column("mixed_audio_url", sa.Text(), nullable=True),
        sa.Column("final_muxed_video_url", sa.Text(), nullable=True),
        sa.Column("local_mixed_audio_path", sa.Text(), nullable=True),
        sa.Column("local_muxed_video_path", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["render_job_id"], ["render_jobs.id"], name=op.f("fk_audio_render_outputs_render_job_id_render_jobs")),
        sa.ForeignKeyConstraint(["narration_job_id"], ["narration_jobs.id"], name=op.f("fk_audio_render_outputs_narration_job_id_narration_jobs")),
        sa.ForeignKeyConstraint(["music_asset_id"], ["music_assets.id"], name=op.f("fk_audio_render_outputs_music_asset_id_music_assets")),
        sa.ForeignKeyConstraint(["mix_profile_id"], ["audio_mix_profiles.id"], name=op.f("fk_audio_render_outputs_mix_profile_id_audio_mix_profiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_render_outputs")),
    )
    op.create_index(op.f("ix_audio_render_outputs_render_job_id"), "audio_render_outputs", ["render_job_id"], unique=False)
    op.create_index(op.f("ix_audio_render_outputs_narration_job_id"), "audio_render_outputs", ["narration_job_id"], unique=False)
    op.create_index(op.f("ix_audio_render_outputs_music_asset_id"), "audio_render_outputs", ["music_asset_id"], unique=False)
    op.create_index(op.f("ix_audio_render_outputs_mix_profile_id"), "audio_render_outputs", ["mix_profile_id"], unique=False)
    op.create_index(op.f("ix_audio_render_outputs_status"), "audio_render_outputs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audio_render_outputs_status"), table_name="audio_render_outputs")
    op.drop_index(op.f("ix_audio_render_outputs_mix_profile_id"), table_name="audio_render_outputs")
    op.drop_index(op.f("ix_audio_render_outputs_music_asset_id"), table_name="audio_render_outputs")
    op.drop_index(op.f("ix_audio_render_outputs_narration_job_id"), table_name="audio_render_outputs")
    op.drop_index(op.f("ix_audio_render_outputs_render_job_id"), table_name="audio_render_outputs")
    op.drop_table("audio_render_outputs")

    op.drop_index(op.f("ix_audio_mix_profiles_display_name"), table_name="audio_mix_profiles")
    op.drop_table("audio_mix_profiles")

    op.drop_index(op.f("ix_music_assets_mood"), table_name="music_assets")
    op.drop_index(op.f("ix_music_assets_display_name"), table_name="music_assets")
    op.drop_table("music_assets")

    op.drop_index(op.f("ix_narration_segments_narration_job_id"), table_name="narration_segments")
    op.drop_table("narration_segments")

    op.drop_index(op.f("ix_narration_jobs_provider_job_id"), table_name="narration_jobs")
    op.drop_index(op.f("ix_narration_jobs_status"), table_name="narration_jobs")
    op.drop_index(op.f("ix_narration_jobs_voice_profile_id"), table_name="narration_jobs")
    op.drop_index(op.f("ix_narration_jobs_render_job_id"), table_name="narration_jobs")
    op.drop_table("narration_jobs")

    op.drop_index(op.f("ix_voice_samples_voice_profile_id"), table_name="voice_samples")
    op.drop_table("voice_samples")

    op.drop_index(op.f("ix_voice_profiles_is_active"), table_name="voice_profiles")
    op.drop_index(op.f("ix_voice_profiles_consent_status"), table_name="voice_profiles")
    op.drop_index(op.f("ix_voice_profiles_owner_user_id"), table_name="voice_profiles")
    op.drop_index(op.f("ix_voice_profiles_provider_voice_id"), table_name="voice_profiles")
    op.drop_index(op.f("ix_voice_profiles_display_name"), table_name="voice_profiles")
    op.drop_table("voice_profiles")
