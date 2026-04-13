BEGIN;

CREATE TABLE IF NOT EXISTS template_packs (
    id UUID PRIMARY KEY,
    template_name TEXT NOT NULL,
    template_type TEXT NOT NULL DEFAULT 'composite',
    source_project_id UUID NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    description TEXT NULL,
    reusability_score NUMERIC(5,2) NULL,
    performance_score NUMERIC(5,2) NULL,
    usage_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_versions (
    id UUID PRIMARY KEY,
    template_pack_id UUID NOT NULL REFERENCES template_packs(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    change_notes TEXT NULL,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(template_pack_id, version_no)
);

CREATE TABLE IF NOT EXISTS style_templates (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NULL,
    aspect_ratio TEXT NOT NULL,
    visual_identity_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_scene_count INTEGER NOT NULL DEFAULT 5,
    default_duration_sec NUMERIC(10,2) NOT NULL DEFAULT 5.0,
    voice_profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    thumbnail_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS narrative_templates (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NULL,
    hook_formula TEXT NULL,
    structure_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    slot_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    cta_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scene_blueprints (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NULL,
    scene_count INTEGER NOT NULL,
    blueprint_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    timeline_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS character_packs (
    id UUID PRIMARY KEY,
    pack_name TEXT NOT NULL,
    description TEXT NULL,
    identity_summary TEXT NULL,
    appearance_lock_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reference_assets_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    pose_variants_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    expression_variants_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    usage_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thumbnail_templates (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NULL,
    layout_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    headline_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    crop_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS publishing_templates (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    description TEXT NULL,
    publishing_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    title_pattern TEXT NULL,
    description_pattern TEXT NULL,
    hashtags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    upload_defaults_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_components (
    id UUID PRIMARY KEY,
    template_version_id UUID NOT NULL REFERENCES template_versions(id) ON DELETE CASCADE,
    component_type TEXT NOT NULL,
    component_id UUID NOT NULL,
    component_role TEXT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_extractions (
    id UUID PRIMARY KEY,
    source_project_id UUID NOT NULL,
    template_pack_id UUID NULL REFERENCES template_packs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    extraction_report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    score_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_usage_runs (
    id UUID PRIMARY KEY,
    template_pack_id UUID NOT NULL REFERENCES template_packs(id) ON DELETE CASCADE,
    template_version_id UUID NOT NULL REFERENCES template_versions(id) ON DELETE CASCADE,
    project_id UUID NOT NULL,
    mode TEXT NOT NULL DEFAULT 'single',
    input_slots_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_performance_snapshots (
    id UUID PRIMARY KEY,
    template_pack_id UUID NOT NULL REFERENCES template_packs(id) ON DELETE CASCADE,
    snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_clone_jobs (
    id UUID PRIMARY KEY,
    template_pack_id UUID NOT NULL REFERENCES template_packs(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'batch',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_template_packs_status ON template_packs(status);
CREATE INDEX IF NOT EXISTS idx_template_versions_pack_active ON template_versions(template_pack_id, is_active);
CREATE INDEX IF NOT EXISTS idx_template_usage_runs_pack_status ON template_usage_runs(template_pack_id, status);
CREATE INDEX IF NOT EXISTS idx_template_extractions_source_project ON template_extractions(source_project_id);
CREATE INDEX IF NOT EXISTS idx_template_clone_jobs_status ON template_clone_jobs(status);
CREATE INDEX IF NOT EXISTS idx_template_components_version_type ON template_components(template_version_id, component_type);
CREATE INDEX IF NOT EXISTS idx_template_perf_snapshots_pack_time ON template_performance_snapshots(template_pack_id, captured_at DESC);

COMMIT;
