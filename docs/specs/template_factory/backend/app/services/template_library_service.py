from __future__ import annotations
import uuid
from app.db.models.template_factory import TemplatePack, TemplateVersion
from app.repositories.template_factory_repo import TemplateFactoryRepository

class TemplateLibraryService:
    def __init__(self, repo: TemplateFactoryRepository):
        self.repo = repo

    def create_template(self, payload: dict) -> TemplatePack:
        pack = TemplatePack(
            id=uuid.uuid4(),
            template_name=payload["template_name"],
            template_type=payload.get("template_type", "composite"),
            description=payload.get("description"),
            metadata_json=payload.get("metadata_json", {}),
        )
        return self.repo.create_template_pack(pack)

    def list_templates(self, status: str | None = None):
        return self.repo.list_template_packs(status=status)

    def create_version(self, template_id, payload: dict) -> TemplateVersion:
        active = self.repo.get_active_version(template_id)
        next_version = (active.version_no + 1) if active else 1
        version = TemplateVersion(
            id=uuid.uuid4(),
            template_pack_id=template_id,
            version_no=next_version,
            change_notes=payload.get("change_notes"),
            config_json=payload.get("config_json", {}),
            is_active=True,
        )
        return self.repo.create_template_version(version)
