backend/
└── app/
    ├── api/
    │   └── v1/
    │       ├── templates.py
    │       ├── style_templates.py
    │       ├── narrative_templates.py
    │       ├── scene_blueprints.py
    │       ├── character_packs.py
    │       ├── thumbnail_templates.py
    │       └── publishing_templates.py
    ├── db/
    │   ├── models/
    │   │   ├── template_pack.py
    │   │   ├── template_version.py
    │   │   ├── style_template.py
    │   │   ├── narrative_template.py
    │   │   ├── scene_blueprint.py
    │   │   ├── character_pack.py
    │   │   ├── thumbnail_template.py
    │   │   ├── publishing_template.py
    │   │   └── template_ops.py
    │   └── migrations/
    │       └── 001_template_factory_layer.sql
    ├── repositories/
    │   ├── template_pack_repo.py
    │   ├── template_version_repo.py
    │   ├── template_component_repo.py
    │   ├── template_extraction_repo.py
    │   ├── template_usage_run_repo.py
    │   └── template_clone_job_repo.py
    ├── schemas/
    │   ├── template_pack.py
    │   ├── template_generation.py
    │   ├── template_extraction.py
    │   └── template_analytics.py
    ├── services/
    │   ├── template_extraction_service.py
    │   ├── template_library_service.py
    │   ├── template_generation_service.py
    │   ├── template_batch_service.py
    │   ├── template_scoring_service.py
    │   └── template_analytics_service.py
    ├── workers/
    │   ├── template_extraction_worker.py
    │   ├── template_generation_worker.py
    │   ├── template_batch_worker.py
    │   └── template_analytics_worker.py
    └── events/
        ├── template.extract.requested.json
        ├── template.extract.completed.json
        ├── template.extract.failed.json
        ├── template.generate.requested.json
        ├── template.generate.completed.json
        ├── template.generate.failed.json
        ├── template.batch.requested.json
        ├── template.batch.progressed.json
        ├── template.batch.completed.json
        └── template.analytics.snapshot.created.json

frontend/
└── src/
    ├── app/
    │   ├── templates/page.tsx
    │   ├── templates/[id]/page.tsx
    │   ├── templates/extractions/[id]/page.tsx
    │   └── templates/batch/page.tsx
    └── components/
        ├── TemplateLibrary.tsx
        ├── TemplateDetail.tsx
        ├── TemplateExtractionReview.tsx
        ├── TemplateGenerateForm.tsx
        ├── TemplateBatchRunner.tsx
        └── TemplateAnalyticsPanel.tsx
