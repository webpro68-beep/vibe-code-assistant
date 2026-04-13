from __future__ import annotations
import uuid
from app.db.models.template_factory import TemplateCloneJob
from app.repositories.template_factory_repo import TemplateFactoryRepository

class TemplateBatchService:
    def __init__(self, repo: TemplateFactoryRepository):
        self.repo = repo

    def queue_batch(self, template_pack_id, payload: dict) -> TemplateCloneJob:
        clone_job = TemplateCloneJob(
            id=uuid.uuid4(),
            template_pack_id=template_pack_id,
            mode="batch",
            payload_json=payload,
            status="queued",
            result_json={"count": len(payload.get("items", []))},
        )
        return self.repo.create_clone_job(clone_job)
