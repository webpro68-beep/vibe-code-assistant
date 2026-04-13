from __future__ import annotations
import uuid
from app.models.template_factory import TemplateUsageRun
from app.repositories.template_factory_repo import TemplateFactoryRepository

class TemplateGenerationService:
    def __init__(self, repo: TemplateFactoryRepository):
        self.repo = repo

    def generate(self, template_pack_id, payload: dict) -> TemplateUsageRun:
        active = self.repo.get_active_version(template_pack_id)
        if not active:
            raise ValueError("No active template version")
        project_id = uuid.uuid4()
        run = TemplateUsageRun(
            id=uuid.uuid4(),
            template_pack_id=template_pack_id,
            template_version_id=active.id,
            project_id=project_id,
            mode=payload.get("mode", "single"),
            input_slots_json=payload.get("input_slots", {}),
            status="queued",
            result_json={
                "auto_render": payload.get("auto_render", True),
                "auto_upload": payload.get("auto_upload", False),
            },
        )
        return self.repo.create_usage_run(run)
