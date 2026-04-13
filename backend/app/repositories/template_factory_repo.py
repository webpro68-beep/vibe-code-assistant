from __future__ import annotations
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.template_factory import (
    TemplatePack, TemplateVersion, TemplateComponent, TemplateExtraction,
    TemplateUsageRun, TemplateCloneJob
)

class TemplateFactoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_template_pack(self, obj: TemplatePack) -> TemplatePack:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def list_template_packs(self, status: str | None = None) -> list[TemplatePack]:
        stmt = select(TemplatePack)
        if status:
            stmt = stmt.where(TemplatePack.status == status)
        return list(self.db.scalars(stmt).all())

    def get_template_pack(self, template_id) -> TemplatePack | None:
        return self.db.get(TemplatePack, template_id)

    def create_template_version(self, obj: TemplateVersion) -> TemplateVersion:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def activate_template_version(self, template_pack_id, version_id) -> None:
        self.db.execute(update(TemplateVersion).where(TemplateVersion.template_pack_id == template_pack_id).values(is_active=False))
        self.db.execute(update(TemplateVersion).where(TemplateVersion.id == version_id).values(is_active=True))
        self.db.commit()

    def get_active_version(self, template_pack_id) -> TemplateVersion | None:
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_pack_id == template_pack_id,
            TemplateVersion.is_active.is_(True),
        )
        return self.db.scalar(stmt)

    def add_component(self, obj: TemplateComponent) -> TemplateComponent:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def list_components(self, template_version_id) -> list[TemplateComponent]:
        stmt = select(TemplateComponent).where(TemplateComponent.template_version_id == template_version_id)
        return list(self.db.scalars(stmt).all())

    def create_extraction(self, obj: TemplateExtraction) -> TemplateExtraction:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_extraction(self, extraction_id) -> TemplateExtraction | None:
        return self.db.get(TemplateExtraction, extraction_id)

    def create_usage_run(self, obj: TemplateUsageRun) -> TemplateUsageRun:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def create_clone_job(self, obj: TemplateCloneJob) -> TemplateCloneJob:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_clone_job(self, clone_job_id) -> TemplateCloneJob | None:
        return self.db.get(TemplateCloneJob, clone_job_id)
