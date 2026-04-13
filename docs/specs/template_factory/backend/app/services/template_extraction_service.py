from __future__ import annotations
import uuid
from app.db.models.template_factory import TemplateExtraction, TemplatePack, TemplateVersion, TemplateComponent
from app.repositories.template_factory_repo import TemplateFactoryRepository
from app.services.template_scoring_service import TemplateScoringService

class TemplateExtractionService:
    def __init__(self, repo: TemplateFactoryRepository):
        self.repo = repo
        self.scoring = TemplateScoringService()

    def queue_extraction(self, source_project_id, auto_publish: bool = False) -> TemplateExtraction:
        extraction = TemplateExtraction(
            id=uuid.uuid4(),
            source_project_id=source_project_id,
            status="queued",
            extraction_report_json={"auto_publish": auto_publish},
        )
        return self.repo.create_extraction(extraction)

    def perform_extraction(self, extraction_id) -> dict:
        extraction = self.repo.get_extraction(extraction_id)
        if not extraction:
            raise ValueError("Extraction not found")
        extracted = {
            "style": {"name": "auto-style"},
            "scene_blueprint": {"scene_count": 5},
            "components": [
                {"component_type": "style_template", "component_role": "primary"},
                {"component_type": "scene_blueprint", "component_role": "primary"},
            ],
        }
        score = self.scoring.score_extraction({"source_project_id": str(extraction.source_project_id)}, extracted)
        pack = self.repo.create_template_pack(TemplatePack(
            id=uuid.uuid4(),
            template_name=f"tpl-{extraction.source_project_id}",
            source_project_id=extraction.source_project_id,
            status="published" if extraction.extraction_report_json.get("auto_publish") else "draft",
            reusability_score=score["reusability_score"],
            performance_score=score["performance_score"],
            metadata_json={"source": "template_extraction_worker"},
        ))
        version = self.repo.create_template_version(TemplateVersion(
            id=uuid.uuid4(),
            template_pack_id=pack.id,
            version_no=1,
            is_active=True,
            config_json=extracted,
        ))
        for c in extracted["components"]:
            self.repo.add_component(TemplateComponent(
                id=uuid.uuid4(),
                template_version_id=version.id,
                component_type=c["component_type"],
                component_id=uuid.uuid4(),
                component_role=c.get("component_role"),
                metadata_json={},
            ))
        extraction.template_pack_id = pack.id
        extraction.status = "completed"
        extraction.extraction_report_json = extracted
        extraction.score_json = score
        self.repo.db.commit()
        self.repo.db.refresh(extraction)
        return {"extraction": extraction, "template_pack": pack, "template_version": version}
